"""ChromaDB vector store for semantic search."""

from typing import Optional
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import settings
from ..models import Lead, Carrier, Load


class VectorStore:
    """Vector store for semantic search using ChromaDB."""

    # Collection names
    LEADS_COLLECTION = "leads"
    CARRIERS_COLLECTION = "carriers"
    LOADS_COLLECTION = "loads"
    CONVERSATIONS_COLLECTION = "conversations"

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        use_server: bool = False,
    ):
        """
        Initialize vector store.

        Args:
            persist_dir: Directory for persistent storage (None for in-memory)
            use_server: If True, connect to ChromaDB server instead of local
        """
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR

        if use_server:
            # Connect to ChromaDB server
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
            )
        else:
            # Use persistent local storage
            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )

        # Initialize collections
        self._init_collections()

    def _init_collections(self) -> None:
        """Initialize or get existing collections."""
        # Leads collection - for finding similar carriers/prospects
        self.leads = self.client.get_or_create_collection(
            name=self.LEADS_COLLECTION,
            metadata={
                "description": "Carrier leads for semantic search",
                "hnsw:space": "cosine",
            },
        )

        # Carriers collection - for matching loads to carriers
        self.carriers = self.client.get_or_create_collection(
            name=self.CARRIERS_COLLECTION,
            metadata={
                "description": "Active carriers for load matching",
                "hnsw:space": "cosine",
            },
        )

        # Loads collection - for rate history and lane analysis
        self.loads = self.client.get_or_create_collection(
            name=self.LOADS_COLLECTION,
            metadata={
                "description": "Historical loads for rate prediction",
                "hnsw:space": "cosine",
            },
        )

        # Conversations collection - for context retrieval
        self.conversations = self.client.get_or_create_collection(
            name=self.CONVERSATIONS_COLLECTION,
            metadata={
                "description": "Call/email transcripts for context",
                "hnsw:space": "cosine",
            },
        )

    # =========================================================================
    # Lead Operations
    # =========================================================================

    def add_lead(self, lead: Lead) -> None:
        """Add or update a lead in the vector store."""
        self.leads.upsert(
            ids=[lead.id],
            documents=[lead.to_embedding_text()],
            metadatas=[lead.to_search_dict()],
        )

    def add_leads(self, leads: list[Lead]) -> None:
        """Batch add leads to vector store."""
        if not leads:
            return

        self.leads.upsert(
            ids=[lead.id for lead in leads],
            documents=[lead.to_embedding_text() for lead in leads],
            metadatas=[lead.to_search_dict() for lead in leads],
        )

    def search_leads(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        Search leads by semantic similarity.

        Args:
            query: Search query text
            n_results: Number of results to return
            where: Optional filter conditions

        Returns:
            List of matching lead metadata with distances
        """
        results = self.leads.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )

        # Format results
        matches = []
        if results["ids"] and results["ids"][0]:
            for i, lead_id in enumerate(results["ids"][0]):
                match = {
                    "id": lead_id,
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "document": results["documents"][0][i] if results["documents"] else None,
                }
                if results["metadatas"] and results["metadatas"][0]:
                    match.update(results["metadatas"][0][i])
                matches.append(match)

        return matches

    def find_similar_leads(
        self,
        lead: Lead,
        n_results: int = 5,
        exclude_self: bool = True,
    ) -> list[dict]:
        """Find leads similar to a given lead."""
        results = self.search_leads(
            query=lead.to_embedding_text(),
            n_results=n_results + (1 if exclude_self else 0),
        )

        if exclude_self:
            results = [r for r in results if r["id"] != lead.id][:n_results]

        return results

    def delete_lead(self, lead_id: str) -> None:
        """Delete a lead from vector store."""
        self.leads.delete(ids=[lead_id])

    # =========================================================================
    # Carrier Operations
    # =========================================================================

    def add_carrier(self, carrier: Carrier) -> None:
        """Add or update a carrier in the vector store."""
        metadata = {
            "id": carrier.id,
            "company_name": carrier.company_name,
            "mc_number": carrier.authority.mc_number,
            "truck_count": carrier.fleet.truck_count,
            "equipment_types": ",".join(str(e) for e in carrier.fleet.equipment_types),
            "current_location_state": carrier.current_location_state or "",
            "home_base_state": carrier.fleet.home_base_state or "",
            "is_available": carrier.is_available,
            "status": carrier.status,
            "reliability_score": carrier.performance.reliability_score,
            "min_rate_per_mile": carrier.preferences.min_rate_per_mile,
        }

        self.carriers.upsert(
            ids=[carrier.id],
            documents=[carrier.to_embedding_text()],
            metadatas=[metadata],
        )

    def search_carriers(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """Search carriers by semantic similarity."""
        results = self.carriers.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )

        matches = []
        if results["ids"] and results["ids"][0]:
            for i, carrier_id in enumerate(results["ids"][0]):
                match = {
                    "id": carrier_id,
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "document": results["documents"][0][i] if results["documents"] else None,
                }
                if results["metadatas"] and results["metadatas"][0]:
                    match.update(results["metadatas"][0][i])
                matches.append(match)

        return matches

    def find_carriers_for_load(
        self,
        load: Load,
        n_results: int = 10,
        available_only: bool = True,
    ) -> list[dict]:
        """
        Find best carriers for a given load.

        Uses semantic search to find carriers whose profile matches the load.
        """
        # Build search query from load details
        query = (
            f"Carrier needed for {load.origin} to {load.destination} | "
            f"{load.loaded_miles} miles | {load.equipment_type} | "
            f"{load.commodity} | ${load.rate_per_mile}/mi"
        )

        where = None
        if available_only:
            where = {"is_available": True}

        return self.search_carriers(query=query, n_results=n_results, where=where)

    # =========================================================================
    # Load Operations
    # =========================================================================

    def add_load(self, load: Load) -> None:
        """Add or update a load in the vector store."""
        metadata = {
            "id": load.id,
            "lane": load.lane,
            "origin_state": load.origin.state,
            "destination_state": load.destination.state,
            "loaded_miles": load.loaded_miles,
            "rate": load.rate,
            "rate_per_mile": load.rate_per_mile,
            "equipment_type": str(load.equipment_type),
            "commodity": load.commodity,
            "halal_status": load.halal_status,
            "status": load.status,
            "broker_name": load.broker.company_name,
            "pickup_date": load.pickup_window.earliest.isoformat(),
        }

        self.loads.upsert(
            ids=[load.id],
            documents=[load.to_embedding_text()],
            metadatas=[metadata],
        )

    def search_loads(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """Search loads by semantic similarity."""
        results = self.loads.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )

        matches = []
        if results["ids"] and results["ids"][0]:
            for i, load_id in enumerate(results["ids"][0]):
                match = {
                    "id": load_id,
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "document": results["documents"][0][i] if results["documents"] else None,
                }
                if results["metadatas"] and results["metadatas"][0]:
                    match.update(results["metadatas"][0][i])
                matches.append(match)

        return matches

    def get_rate_history(
        self,
        lane: str,
        equipment_type: Optional[str] = None,
        n_results: int = 20,
    ) -> list[dict]:
        """
        Get historical rates for a lane.

        Args:
            lane: Lane string (e.g., "TX-CA")
            equipment_type: Optional equipment filter
            n_results: Number of results

        Returns:
            List of historical loads with rates
        """
        where = {"lane": lane}
        if equipment_type:
            where["equipment_type"] = equipment_type

        results = self.loads.query(
            query_texts=[f"Rate history for {lane}"],
            n_results=n_results,
            where=where,
        )

        matches = []
        if results["metadatas"] and results["metadatas"][0]:
            for metadata in results["metadatas"][0]:
                matches.append(metadata)

        return matches

    def estimate_lane_rate(
        self,
        origin_state: str,
        destination_state: str,
        equipment_type: str = "dry_van",
    ) -> dict:
        """
        Estimate rate for a lane based on historical data.

        Returns:
            Dict with min, max, avg, and recommended rates
        """
        lane = f"{origin_state.upper()}-{destination_state.upper()}"
        history = self.get_rate_history(lane, equipment_type)

        if not history:
            # No history, use defaults
            return {
                "lane": lane,
                "equipment_type": equipment_type,
                "sample_size": 0,
                "min_rate": settings.MIN_RATE_PER_MILE,
                "max_rate": settings.TARGET_RATE_PER_MILE,
                "avg_rate": settings.SOFT_FLOOR_RATE,
                "recommended_rate": settings.TARGET_RATE_PER_MILE,
            }

        rates = [h.get("rate_per_mile", 0) for h in history if h.get("rate_per_mile")]

        if not rates:
            return {
                "lane": lane,
                "equipment_type": equipment_type,
                "sample_size": 0,
                "min_rate": settings.MIN_RATE_PER_MILE,
                "max_rate": settings.TARGET_RATE_PER_MILE,
                "avg_rate": settings.SOFT_FLOOR_RATE,
                "recommended_rate": settings.TARGET_RATE_PER_MILE,
            }

        avg_rate = sum(rates) / len(rates)
        min_rate = min(rates)
        max_rate = max(rates)

        # Recommended rate is slightly above average but below max
        recommended = avg_rate * 1.05  # 5% above average

        return {
            "lane": lane,
            "equipment_type": equipment_type,
            "sample_size": len(rates),
            "min_rate": round(min_rate, 2),
            "max_rate": round(max_rate, 2),
            "avg_rate": round(avg_rate, 2),
            "recommended_rate": round(recommended, 2),
        }

    # =========================================================================
    # Conversation Operations
    # =========================================================================

    def add_conversation(
        self,
        conversation_id: str,
        text: str,
        metadata: dict,
    ) -> None:
        """Add a conversation transcript to vector store."""
        self.conversations.upsert(
            ids=[conversation_id],
            documents=[text],
            metadatas=[metadata],
        )

    def search_conversations(
        self,
        query: str,
        carrier_id: Optional[str] = None,
        n_results: int = 5,
    ) -> list[dict]:
        """Search conversation history."""
        where = None
        if carrier_id:
            where = {"carrier_id": carrier_id}

        results = self.conversations.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )

        matches = []
        if results["ids"] and results["ids"][0]:
            for i, conv_id in enumerate(results["ids"][0]):
                match = {
                    "id": conv_id,
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "document": results["documents"][0][i] if results["documents"] else None,
                }
                if results["metadatas"] and results["metadatas"][0]:
                    match.update(results["metadatas"][0][i])
                matches.append(match)

        return matches

    # =========================================================================
    # Utility Operations
    # =========================================================================

    def get_collection_stats(self) -> dict:
        """Get statistics about all collections."""
        return {
            "leads": self.leads.count(),
            "carriers": self.carriers.count(),
            "loads": self.loads.count(),
            "conversations": self.conversations.count(),
        }

    def clear_collection(self, collection_name: str) -> None:
        """Clear all data from a collection."""
        collection_map = {
            "leads": self.leads,
            "carriers": self.carriers,
            "loads": self.loads,
            "conversations": self.conversations,
        }

        if collection_name in collection_map:
            # Delete and recreate
            self.client.delete_collection(collection_name)
            self._init_collections()

    def reset_all(self) -> None:
        """Reset all collections (use with caution!)."""
        for name in [
            self.LEADS_COLLECTION,
            self.CARRIERS_COLLECTION,
            self.LOADS_COLLECTION,
            self.CONVERSATIONS_COLLECTION,
        ]:
            try:
                self.client.delete_collection(name)
            except Exception:
                pass  # Collection might not exist
        self._init_collections()


@lru_cache
def get_vector_store() -> VectorStore:
    """Get cached vector store instance."""
    return VectorStore()
