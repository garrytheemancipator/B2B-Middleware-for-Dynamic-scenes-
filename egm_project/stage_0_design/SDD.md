# System Design Document (SDD): 3D Dynamic Scene Ingestion Pipeline

## 1. Overview
This document defines the architecture for the **Ingestion Pipeline**, the foundation of the EGM (Elephant-Goldfish Model) Stage 1 roadmap. The pipeline provides a standardized, scalable B2B middleware for normalizing, temporal-aligning, and storing multi-modal 3D spatial data (NeRF, 3DGS, RadSplat, point-cloud mapping) for downstream dynamic scene rendering.

## 2. Architectural Vision
The system adopts an asynchronous, distributed event-driven architecture to handle high-bandwidth raw sensor data while ensuring strict temporal synchronization across disparate input modalities.

### 2.1 Component Boundaries
*   **Ingestion Gateway:** Entry point for authenticated clients. Manages rate limiting, schema validation, and initial payload verification.
*   **Orchestration Engine:** Manages task distribution, state transitions, and workflow retries using a high-throughput streaming bus (e.g., Redis Streams or Aeron cluster).
*   **Normalization Service:** Decouples specific sensor/vendor formats into a unified internal intermediate representation (IR). Nodes are hardened using Confidential Computing (TEE/gVisor).
*   **Temporal Sync Engine:** Critical path component. Aligning time-stamps across asynchronous streams (e.g., lidar at 10Hz, video at 60fps) using interpolation/extrapolation.
*   **Storage Tier:**
    *   *Cold/BLOB:* Raw sensor streams, high-res point clouds, textures. Includes an automated TTL-based janitor policy for cleaning orphaned segments.
    *   *Metadata/Temporal Index:* Graph-based index for spatial-temporal query acceleration.

## 3. Data Schema & Mapping
The pipeline centralizes data around a **Spatio-Temporal Frame (STF)** unit.

*   **Header:** `AssetID`, `Timestamp_Global`, `SensorID`, `CoordSystem_Origin`.
*   **Spatial Payload:** 
    *   Dense/Sparse Point Cloud (XYZ+RGBA/Features).
    *   Gaussian Splat Parameters (Rotation, Scale, Opacity, Spherical Harmonics).
*   **Temporal Context:** Relative displacement vector between frames $T_n$ and $T_{n+1}$.
*   **Mapping Convention:** All incoming local coordinate systems must be mapped to a global scene anchor point via a transformation matrix $M_{transform}$ recorded at each ingestion transaction. All such transformations must be cryptographically signed and bounded.

## 4. Ingestion Workflow
1.  **Submission:** Client pushes raw payload to the Ingestion Gateway via S3-signed URL or authenticated streaming stream.
2.  **Verification:** Ingestion Gateway validates format, integrity (checksum), and temporal headers.
3.  **Normalization:** The Normalized Service converts raw data into STF chunks within hardened TEE/gVisor execution environments.
Temporal Alignment: Temporal Sync Engine resolves drift and applies sync constraints based on the `Timestamp_Global`. Formalize global reference clock verification for drift compensation (e.g., cryptographically signed reference).
5.  **Persistence:** Normalized STFs are flushed to BLOB storage, and metadata updates are committed to the Index DB.
6.  **Callback:** Orchestration engine signals completion/failure to the client API endpoint.

## 5. Scalability & Reliability
*   **Idempotency:** Each ingestion request includes a client-generated UUID for the specific temporal frame. Re-submissions of the same UUID are deduped at the gateway level.
*   **Backpressure:** The orchestration engine monitors worker queue depth, pushing back against ingestion rates during high-load periods to prevent memory overflow in normalization nodes.
*   **Checkpointing:** Every processing step writes its state to the orchestrator's state store; failures result in resuming from the last successful pipeline stage rather than full-ingestion restarts.
*   **Janitor Policy:** Automated TTL-based cleanup of orphaned BLOB segments in the storage tier to prevent resource bloat.

## 6. Security & Compliance
*   **Isolation:** Each tenant's ingestion bucket is logically isolated using scoped credentials.
*   **Encryption:** Data is encrypted at rest (AES-256) and in transit (TLS 1.3).
*   **Audit Logging:** Every stage transition (Received → Validated → Normalizing → Aligned → Persisted) is logged with its duration for latency tracking and cost attribution.
*   **Transformation Integrity:** All coordinate transformation matrices $M_{transform}$ are cryptographically signed at origin and bounded to prevent out-of-bounds scene distortion.
*   **Tenant Resource Management:** Implement per-tenant rate-limiting and resource quotas within the Middleware Orchestrator to prevent abuse and ensure fair resource distribution.
*   **RBAC Hardening:** Strengthen Role-Based Access Control (RBAC) for the B2B dashboard to enforce granular permissions and minimize privilege escalation vectors.
*   **Control Plane Security:** Harden the Middleware Orchestrator's control plane against unauthorized access and command injection.

## 7. Stage 4: Rendering Engine Integration & Middleware Scaling

### 7.1 Middleware Orchestrator
The Middleware Orchestrator extends the ingestion pipeline's control plane to manage high-compute rendering tasks. It acts as a job scheduler that dispatches workloads to GPU-accelerated clusters for NeRF, 3DGS, and RadSplat processing.

*   **Task Management:** Translates high-level scene rendering requests into optimized DAG (Directed Acyclic Graph) of GPU tasks.
*   **Resource Allocation:** Dynamically scales compute pods based on rendering throughput and scene complexity.
*   **GPU Scheduling:** Implements affinity-aware scheduling to ensure optimal utilization of specific hardware acceleration (e.g., CUDA-cores for RadSplat/3DGS).
*   **GPU Isolation Strategy:** Define and implement a strict GPU isolation strategy (e.g., namespace-based partitioning or strict containerization per task) to prevent resource contention and security breaches between rendering jobs.

### 7.2 B2B Scene Management Dashboard
The B2B Dashboard provides a unified interface for clients to manage their 3D scene assets and monitor rendering pipelines.

*   **Scene Asset Browser:** Visual representation of ingested 3D assets, categorized by spatial-temporal frames.
*   **Pipeline Monitoring:** Real-time dashboard showing the status of ingestion, rendering tasks, and storage utilization.
*   **Rendering Configuration:** Interface for parameter tuning of NeRF/3DGS models (e.g., view count, sampling density).
*   **User/Tenant Management:** Role-based access control (RBAC) and quota monitoring for multi-tenant environments.

---

*Document Status: Updated (Stage 4).*