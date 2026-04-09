# Job Reco System

## Introduction
Job Reco System is an AI-powered backend application that analyzes resume content and returns role recommendations with confidence scoring.

The platform is designed for reliability in production-like conditions:
- It extracts skills from resumes using AI with deterministic fallback logic.
- It ranks jobs with strict domain-aware scoring to reduce false matches.
- It always returns a stable response shape for frontend integration.

## Features
- Resume parsing and text extraction from uploaded PDF files
- AI-based skill extraction with safe fallback when external APIs fail
- Caching and timeout handling for external AI calls
- Strict skill matching to prevent weak partial-match hallucinations
- Weighted recommendation scoring with minimum relevance thresholds
- Domain validation (AI, Backend, Cybersecurity) before boost application
- Low-score filtering to suppress unrelated job suggestions
- Guaranteed non-empty response contract for API consumers
- Featured job selection with quick apply links
- Market insights and skill-gap suggestions with fallback support
- Structured backend logging for extracted skills, scores, and API failures
- Django test coverage for recommendation behavior and endpoint reliability
