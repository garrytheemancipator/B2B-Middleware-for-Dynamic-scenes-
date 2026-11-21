# Interface Contract: EGM Normalized Intermediate Representation (IR)

## 1. Overview
The Normalized Intermediate Representation (IR) serves as the unified data format for the EGM ingestion pipeline, facilitating communication between the **Ingestion Gateway** and the **Normalization Service**.

## 2. Spatio-Temporal Frame (STF) Schema (Protocol Buffers)

```protobuf
syntax = "proto3";

package egm.v1;

import "google/protobuf/timestamp.proto";

// Normalized Spatio-Temporal Frame (STF)
message STF {
  string frame_id = 1;
  google.protobuf.timestamp timestamp = 2;
  
  // Drift Compensation
  double temporal_drift_offset_ms = 3;
  
  // Data Payloads
  oneof representation {
    NeRFDensityField nerf_data = 4;
    GaussianSplatData splat_data = 5;
  }
  
  // Cryptographic Proof
  bytes signature = 6;
  string public_key_id = 7;
}

message NeRFDensityField {
  bytes voxel_grid_data = 1;
  float density_threshold = 2;
}

message GaussianSplatData {
  uint32 point_count = 1;
  // Packed as [x, y, z, rot_x, rot_y, rot_z, rot_w, scale_x, scale_y, scale_z, opacity, r, g, b]
  bytes sh_coefficients = 2; 
}
```

## 3. Ingestion Gateway API Contract

### Service: NormalizationIngestion
`POST /v1/ingest`

**Request:**
```json
{
  "source_metadata": {
    "device_id": "string",
    "session_id": "string",
    "transformation_matrix": "float[16]"
  },
  "stf_payload": {
    "frame_id": "UUID",
    "data_type": "3DGS | NERF",
    "blob_url": "s3://..."
  },
  "signature": "base64"
}
```

**Response:**
```json
{
  "status": "ACCEPTED | REJECTED",
  "request_id": "UUID",
  "error": "optional"
}
```

## 4. Invariant Rules
1. **Signature Enforcement**: All `STF` payloads must be cryptographically signed by the originating hardware source.
2. **Temporal Sync**: `temporal_drift_offset_ms` must be calculated against the PTP (Precision Time Protocol) master clock.
3. **Payload Immutability**: Once an STF is ingested, it is considered immutable. Modifications require a new `frame_id`.
