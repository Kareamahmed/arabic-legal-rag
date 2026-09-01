from .VectorDBEnums import VectorDBEnums
from .providers import PGvectorProvider
from helper.config import Settings


class VectorDBFactory:
    def __init__(self, db_client, settings: Settings):
        self.db_client = db_client
        self.settings = settings

    def create_provider(self, name):
        if name == VectorDBEnums.PGVECTOR.value:
            return PGvectorProvider(
                db_client=self.db_client,
                distance_metric=self.settings.VECTOR_DISTANCE_METRIC,
                index_threshold=self.settings.VECTOR_DB_PGVECT_INDEX_THRESHOLD,
            )

        return None
