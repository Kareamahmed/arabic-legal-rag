from enum import Enum


class VectorDBEnums(Enum):
    PGVECTOR = "pgvector"


class DistanceMetricEnums(Enum):
    COSINE = "cosine"
    DOT = "dot"


class PgvectorTableSchemaEnums(Enum):
    ID = "id"
    CHUNK_ID = "chunk_id"
    TEXT = "text"
    VECTOR = "vector"
    TSV = "tsv"


class PgvectorDistanceMetricEnums(Enum):
    COSINE = "vector_cosine_ops"
    L2 = "vector_l2_ops"


class PgvectorIndexTypeEnums(Enum):
    IVFFLAT = "ivfflat"
    HNSW = "hnsw"


class PgvectorTextSearchConfigEnums(Enum):
    SIMPLE = "simple"
    ENGLISH = "english"
    ARABIC = "arabic"
