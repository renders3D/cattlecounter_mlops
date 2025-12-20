# 📑 Technical Report: Phase 2 - Cloud Architecture & MLOps Implementation

**Date:** December 2025

**Project:** CattleCounter (Aerial Livestock Monitoring)

**Phase:** MLOps & Production Deployment

**Author:** Carlos Luis Noriega - Lead AI Engineer

## 1. Executive Summary

Following the successful validation of the DETR Transformer model (Phase 1), Phase 2 focused on architecting a scalable, cloud-native system capable of processing large video files asynchronously. We successfully transitioned from local scripts to a distributed microservices architecture on Azure, implementing a robust CI/CD pipeline and full observability.

## 2. System Architecture

We adopted an Asynchronous Producer-Consumer Pattern to decouple video ingestion from heavy AI processing.

Components:

**Producer (API):** A lightweight FastAPI service deployed on Azure Web Apps (Linux). It handles video intake via streaming to prevent RAM saturation.

**Broker (Queue):** Azure Queue Storage acts as the buffer, ensuring no jobs are lost if the worker is busy or restarting.

**Consumer (Worker):** A Python container running on Azure Container Instances (ACI). It pulls jobs, downloads footage, runs the DETR inference (PyTorch), and uploads results.

**Frontend (Ops Center):** A Streamlit dashboard providing real-time upload progress, processing status, and historical data analytics.

## 3. Key Technical Challenges & Solutions

During the implementation, we encountered and solved critical engineering bottlenecks:

1. The "Large File" Timeout

    **Problem:** Uploading high-resolution drone footage (>500MB) caused timeouts in the API and Azure SDKs due to memory buffering.

    **Solution:** Implemented Streaming Uploads.

    * **Frontend:** Used requests-toolbelt to stream bytes from the browser to the API with real-time progress tracking.

    * **Backend:** Configured FastAPI and Azure Blob Client to stream data chunks (max_concurrency=4) directly to storage without loading the entire file into RAM.

2. The "Zombie Queue" & Resilience

    **Problem:** Worker crashes or network failures left "invisible" messages in the queue that reappeared minutes later, causing duplicate processing loops.

    **Solution:** Implemented aggressive Visibility Timeouts (15 mins) and an Auto-Healing Infrastructure mechanism in the code. The system checks and recreates Queues/Containers automatically if they are accidentally deleted or missing.

3. Observability Blind Spots

    **Problem:** The user had no visibility into the AI inference progress (black box).

    **Solution:** Implemented a Sidecar Status Pattern. The Worker periodically uploads a lightweight JSON (video_status.json) to Blob Storage. The Dashboard polls this file to render a synchronized progress bar.

## 4. CI/CD Pipeline (DevOps)

We established a GitHub Actions pipeline (deploy.yml) that:

* Builds optimized Docker images (Multi-stage builds).

* Pushes artifacts to Azure Container Registry (ACR).

* Deploys the API to Azure Web Apps and the Worker to ACI.

* Injects environment variables and secrets securely at runtime.

*Note: We migrated infrastructure to the West Europe region to comply with Azure Student subscription quotas.*

## 5. Conclusion & Next Steps

The system is now fully operational in a production environment. It handles end-to-end processing with zero manual intervention.

Immediate Next Steps:

**Data Collection:** Awaiting field dataset (zenithal drone footage).

**Phase 3:** *Fine-tuning* the DETR model on the Hugging Face Hub using the collected data to improve accuracy on crowded herds.