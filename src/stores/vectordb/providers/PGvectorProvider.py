from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import (
    DistanceMetricEnums,
    PgvectorDistanceMetricEnums,
    PgvectorTableSchemaEnums,
    PgvectorTextSearchConfigEnums,
)
import logging
from sqlalchemy import text as sql_text
from models.db_schemes.arabic_legal.schemes import RetrievedDocument


class PGvectorProvider(VectorDBInterface):

    def __init__(
        self, db_client, distance_metric: str = None, index_threshold: int = 10000
    ):
        self.db_client = db_client
        self.index_threshold = index_threshold

        if distance_metric == DistanceMetricEnums.COSINE.value:
            self.distance_metric = PgvectorDistanceMetricEnums.COSINE.value
        else:
            self.distance_metric = PgvectorDistanceMetricEnums.L2.value

        self.logger = logging.getLogger("uvicorn")
        self.text_search_config = PgvectorTextSearchConfigEnums.ARABIC.value

    async def connect(self):
        async with self.db_client() as session:
            async with session.begin():
                await session.execute(sql_text("create extension if not exists vector"))

    async def is_table_exists(self, table_name):
        async with self.db_client() as session:
            query = sql_text("select * from pg_tables where tablename = :table_name")
            result = await session.execute(query, {"table_name": table_name})
            return result.scalar_one_or_none()

    async def get_table_info(self, table_name):
        async with self.db_client() as session:
            table_info_sql = sql_text(
                "SELECT * FROM pg_tables where tablename = :table_name"
            )
            table_info_results = await session.execute(
                table_info_sql, {"table_name": table_name}
            )
            table_info = table_info_results.mappings().one_or_none()
            if table_info is None:
                return None

            safe_table_name = table_name.replace('"', '""')
            count_sql = sql_text(f'select count(*) from "{safe_table_name}"')
            count_results = await session.execute(count_sql)
            count_rows = count_results.scalar_one_or_none()

            return {
                "table_info": dict(table_info),
                "count_rows": count_rows,
            }

    async def delete_table(self, table_name):

        if not await self.is_table_exists(table_name=table_name):
            self.logger.error(f"Table {table_name} does not exist.")
            return False

        async with self.db_client() as session:
            async with session.begin():
                query = sql_text(f"drop table if exists {table_name}")
                await session.execute(query)
                self.logger.info(f"Table {table_name} deleted successfully")

        return True

    async def create_table(self, table_name, embed_size, do_reset=False):
        if do_reset:
            await self.delete_table(table_name=table_name)
        is_table_exists = await self.is_table_exists(table_name=table_name)

        if not is_table_exists:
            async with self.db_client() as session:
                async with session.begin():
                    id = PgvectorTableSchemaEnums.ID.value
                    chunk_id = PgvectorTableSchemaEnums.CHUNK_ID.value
                    text = PgvectorTableSchemaEnums.TEXT.value
                    tsv = PgvectorTableSchemaEnums.TSV.value
                    vector = PgvectorTableSchemaEnums.VECTOR.value

                    sql = sql_text(f"""
                        CREATE TABLE {table_name} (
                            {id} SERIAL PRIMARY KEY,
                            {chunk_id} INT,
                            {text} TEXT,
                            {vector} VECTOR({embed_size}),
                            {tsv} TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', {self.text_search_config})) STORED,
                            foreign key ({chunk_id}) references chunks(chunk_id) on delete cascade
                        );
                        """)
                    await session.execute(sql)
            self.logger.info(f"Table {table_name} created successfully")
            return True
        return False

    async def insert_many(self, table_name, texts, vectors, chunk_ids, batch_size=100):
        is_table_existed = await self.is_table_exists(table_name=table_name)
        if not is_table_existed:
            self.logger.error(
                f"cannot insert into table {table_name} because it does not exist."
            )
            return False

        if len(texts) != len(vectors):
            self.logger.error("texts and vectors must have the same length.")
            return False

        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i : i + batch_size]
                    batch_vectors = vectors[i : i + batch_size]
                    batch_chunk_ids = chunk_ids[i : i + batch_size]

                    safe_table_name = table_name.replace('"', '""')
                    text_col = PgvectorTableSchemaEnums.TEXT.value
                    vector_col = PgvectorTableSchemaEnums.VECTOR.value
                    chunk_id_col = PgvectorTableSchemaEnums.CHUNK_ID.value

                    values = []
                    for text, vector, chunk_id in zip(
                        batch_texts, batch_vectors, batch_chunk_ids
                    ):
                        values.append(
                            {
                                "text": text,
                                "vector": "["
                                + ",".join([str(v) for v in vector])
                                + "]",
                                "chunk_id": chunk_id,
                            },
                        )
                    sql = sql_text(f"""
                        INSERT INTO "{safe_table_name}" ({text_col}, {vector_col}, {chunk_id_col})
                        VALUES (:text, :vector, :chunk_id);
                        """)
                    await session.execute(sql, values)
        return True

    async def search_by_vector(self, table_name, vector, limit):
        is_table_existed = await self.is_table_exists(table_name=table_name)
        if not is_table_existed:
            self.logger.error(
                f"cannot search in table {table_name} because it does not exist."
            )
            return False

        async with self.db_client() as session:
            async with session.begin():
                safe_table_name = table_name.replace('"', '""')
                text_col = PgvectorTableSchemaEnums.TEXT.value
                vector_col = PgvectorTableSchemaEnums.VECTOR.value
                chunk_id_col = PgvectorTableSchemaEnums.CHUNK_ID.value

                sql = sql_text(f"""
                    SELECT {chunk_id_col},{text_col}, 1 - ({vector_col} <=> :vector) AS score   
                    FROM "{safe_table_name}"
                    ORDER BY score DESC
                    LIMIT :limit;
                    """)
                result = await session.execute(
                    sql,
                    {
                        "vector": "[" + ",".join([str(v) for v in vector]) + "]",
                        "limit": limit,
                    },
                )
                rows = result.fetchall()  # return a list of tuples (text, score)

        if not rows or len(rows) == 0:
            return None
        return [
            RetrievedDocument(chunk_id=row[0], text=row[1], score=row[2])
            for row in rows
        ]

    async def search_by_keyword(self, table_name, text, limit):
        raise NotImplementedError

    async def disconnect(self):
        pass
