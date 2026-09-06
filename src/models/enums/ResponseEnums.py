from enum import Enum


class ResponseEnums(Enum):
    PROCESSING_FAILED = "processing_failed"
    PROCESSING_SUCCESS = "processing_success"
    INDEX_INTO_VECTOR_DB_FAILED = "index_into_vector_db_failed"
    INDEX_INTO_VECTOR_DB_SUCCESS = "index_into_vector_db_success"
    GET_VECTOR_DB_INFO_SUCCESS = "get_vector_db_info_success"
    GET_VECTOR_DB_INFO_FAILED = "get_vector_db_info_failed"
    SEARCH_INTO_VECTOR_DB_FAILED = "search_into_vector_db_failed"
    SEARCH_INTO_VECTOR_DB_SUCCESS = "search_into_vector_db_success"