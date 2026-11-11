import math
from qdrant_client import QdrantClient, models
from app.config import settings

SOURCE_PATH = (
    r"C:\Users\Laksh\Desktop\ResolveAI\backend\data\qdrant"
)
COLLECTION_NAME = settings.qdrant_collection
BATCH_SIZE = 100


def migrate():
    if not settings.qdrant_url or not settings.qdrant_api_key:
        raise RuntimeError("Qdrant Cloud configuration is missing")

    print("Connecting to source and destination...")

    source = QdrantClient(path=SOURCE_PATH)

    destination = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=60,
    )

    try:
        # 1. Verify source collection
        if not source.collection_exists(COLLECTION_NAME):
            raise RuntimeError("Source collection does not exist")

        source_info = source.get_collection(COLLECTION_NAME)
        vector_config = source_info.config.params.vectors

        if not isinstance(vector_config, models.VectorParams):
            raise RuntimeError("Expected a single unnamed vector configuration")

        if vector_config.size != 384:
            raise RuntimeError(
                f"Unexpected vector dimensions: {vector_config.size}"
            )

        print("Source collection verified.")
        print("Vector dimensions:", vector_config.size)
        print("Distance metric:", vector_config.distance)

        # 2. Refuse to overwrite an existing cloud collection
        if destination.collection_exists(COLLECTION_NAME):
            raise RuntimeError(
                "Cloud collection already exists. "
                "Migration stopped to prevent overwriting data."
            )

        # 3. Read all source points, including original vectors
        points = []
        offset = None

        while True:
            batch, next_offset = source.scroll(
                collection_name=COLLECTION_NAME,
                limit=BATCH_SIZE,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )

            points.extend(batch)

            if next_offset is None:
                break

            offset = next_offset

        if not points:
            raise RuntimeError("Source collection contains no points")

        print("Source points found:", len(points))

        # 4. Validate source points before creating cloud collection
        for point in points:
            if point.vector is None or len(point.vector) != 384:
                raise RuntimeError(
                    f"Invalid vector found for point {point.id}"
                )

            if point.payload is None:
                raise RuntimeError(
                    f"Missing payload for point {point.id}"
                )

        # 5. Create cloud collection with matching configuration
        destination.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=vector_config.size,
                distance=vector_config.distance,
            ),
        )

        print("Cloud collection created.")

        # 6. Transfer original IDs, vectors and payloads
        cloud_points = [
            models.PointStruct(
                id=point.id,
                vector=point.vector,
                payload=point.payload,
            )
            for point in points
        ]

        destination.upsert(
            collection_name=COLLECTION_NAME,
            points=cloud_points,
            wait=True,
        )

        print("Vectors uploaded:", len(cloud_points))

        # 7. Independently verify cloud data
        source_by_id = {str(point.id): point for point in points}
        migrated_ids = list(source_by_id.keys())

        verified_points = destination.retrieve(
            collection_name=COLLECTION_NAME,
            ids=migrated_ids,
            with_payload=True,
            with_vectors=True,
        )

        cloud_by_id = {
            str(point.id): point for point in verified_points
        }

        if set(source_by_id) != set(cloud_by_id):
            raise RuntimeError("Point ID verification failed")

        for point_id, original in source_by_id.items():
            migrated = cloud_by_id[point_id]

            if migrated.payload != original.payload:
                raise RuntimeError(
                    f"Payload mismatch for point {point_id}"
                )



        if not all(
            math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-7)
            for a, b in zip(original.vector, migrated.vector)
        ):
            raise RuntimeError(
                f"Vector mismatch for point {point_id}"
            )

        cloud_info = destination.get_collection(COLLECTION_NAME)

        if cloud_info.points_count != len(points):
            raise RuntimeError("Cloud point count verification failed")

        print("\nMIGRATION SUCCESSFUL")
        print("Collection:", COLLECTION_NAME)
        print("Source points:", len(points))
        print("Cloud points:", cloud_info.points_count)
        print("IDs verified: PASS")
        print("Vectors verified: PASS")
        print("Payloads verified: PASS")
        print("Original local collection: UNCHANGED")

    finally:
        source.close()
        destination.close()


if __name__ == "__main__":
    migrate()
