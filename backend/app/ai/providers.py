"""
LLM provider abstraction for requirement extraction and evidence mapping.

The mock provider is deterministic and offline. Gemini is available for real
network calls when configured, while tests can keep using the mock provider
without secrets or network access.
"""

from __future__ import annotations

import asyncio
import json
import re
from abc import ABC, abstractmethod
from typing import Any

from app.config import AIProvider, Settings
from app.ai.prompts import (
    EVIDENCE_MAPPING_SYSTEM_PROMPT,
    REQUIREMENT_EXTRACTION_SYSTEM_PROMPT,
)
from app.models import ApplicationVersion, DocumentChunk, GuidelineVersion, Requirement
from app.models.enums import EvidenceStatus, RequirementCategory, RequirementPriority
from app.utils.errors import raise_error


MANDATORY_CUES = (
    "must",
    "shall",
    "required",
    "applicants must",
    "application must include",
    "must provide",
)
RECOMMENDED_CUES = (
    "recommended",
    "encouraged",
    "advisable",
    "should consider",
    "may consider",
    "preferred",
)


class RequirementExtractionProvider(ABC):
    """Interface implemented by requirement extraction providers."""

    @abstractmethod
    async def extract_requirements(
        self,
        *,
        guideline_version: GuidelineVersion,
        chunks: list[DocumentChunk],
        repair_prompt: str | None = None,
    ) -> str:
        """Return JSON text matching RequirementExtractionPayload."""


class EvidenceMappingProvider(ABC):
    """Interface implemented by evidence mapping providers."""

    @abstractmethod
    async def map_evidence(
        self,
        *,
        application_version: ApplicationVersion,
        requirements: list[Requirement],
        chunks: list[DocumentChunk],
        repair_prompt: str | None = None,
    ) -> str:
        """Return JSON text matching EvidenceMappingPayload."""


class MockRequirementProvider(RequirementExtractionProvider):
    """Deterministic offline requirement extraction provider."""

    async def extract_requirements(
        self,
        *,
        guideline_version: GuidelineVersion,
        chunks: list[DocumentChunk],
        repair_prompt: str | None = None,
    ) -> str:
        requirements = []
        for chunk in sorted(chunks, key=lambda item: item.chunk_index):
            if _is_heading_only_chunk(chunk):
                continue
            for sentence in _requirement_sentences(chunk.text):
                priority = classify_priority(sentence)
                if priority is None:
                    continue
                requirements.append(
                    {
                        "title": _title_from_sentence(sentence),
                        "description": sentence,
                        "category": infer_category(sentence),
                        "priority": priority.value,
                        "source": {
                            "chunk_id": chunk.id,
                            "document": guideline_version.filename,
                            "version": guideline_version.version_number,
                            "page": chunk.page_number,
                            "section": chunk.section_heading,
                        },
                        "source_text": sentence,
                    }
                )
        return json.dumps({"requirements": requirements})


class MockEvidenceProvider(EvidenceMappingProvider):
    """Deterministic offline evidence mapping provider."""

    async def map_evidence(
        self,
        *,
        application_version: ApplicationVersion,
        requirements: list[Requirement],
        chunks: list[DocumentChunk],
        repair_prompt: str | None = None,
    ) -> str:
        mappings = []
        for requirement in sorted(requirements, key=lambda item: item.requirement_id):
            mapping = _map_one_requirement(requirement, application_version, chunks)
            mappings.append(mapping)
        return json.dumps({"mappings": mappings})


class GeminiProvider(RequirementExtractionProvider, EvidenceMappingProvider):
    """Gemini-backed provider for live requirement extraction and evidence mapping."""

    def __init__(self, settings: Settings):
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        self.timeout_seconds = settings.ai_timeout_seconds

    async def extract_requirements(
        self,
        *,
        guideline_version: GuidelineVersion,
        chunks: list[DocumentChunk],
        repair_prompt: str | None = None,
    ) -> str:
        prompt = repair_prompt or REQUIREMENT_EXTRACTION_SYSTEM_PROMPT
        return await self._generate_json(
            system_instruction=prompt,
            user_payload={
                "task": "extract_requirements",
                "response_schema": {
                    "requirements": [
                        {
                            "title": "string",
                            "description": "string",
                            "category": "one RequirementCategory value",
                            "priority": "mandatory or recommended",
                            "source": {
                                "chunk_id": "string",
                                "document": guideline_version.filename,
                                "version": guideline_version.version_number,
                                "page": "integer or null",
                                "section": "string or null",
                            },
                            "source_text": "verbatim quote from the cited chunk",
                        }
                    ]
                },
                "guideline": {
                    "filename": guideline_version.filename,
                    "version": guideline_version.version_number,
                    "chunks": _chunk_payload(chunks),
                },
            },
        )

    async def map_evidence(
        self,
        *,
        application_version: ApplicationVersion,
        requirements: list[Requirement],
        chunks: list[DocumentChunk],
        repair_prompt: str | None = None,
    ) -> str:
        prompt = repair_prompt or EVIDENCE_MAPPING_SYSTEM_PROMPT
        return await self._generate_json(
            system_instruction=prompt,
            user_payload={
                "task": "map_evidence",
                "allowed_statuses": [status.value for status in EvidenceStatus if status != EvidenceStatus.NOT_APPLICABLE],
                "response_schema": {
                    "mappings": [
                        {
                            "requirement_id": "REQ-001",
                            "status": "SUPPORTED, PARTIALLY_SUPPORTED, MISSING, AMBIGUOUS, or CONTRADICTORY",
                            "confidence": "number between 0 and 1",
                            "evidence_text": "verbatim quote from cited chunk, or null for MISSING",
                            "source": "citation object, or null for MISSING",
                            "explanation": "string",
                            "missing_items": ["strings"],
                            "contradictory_evidence": "array or null",
                        }
                    ]
                },
                "application": {
                    "filename": application_version.filename,
                    "version": application_version.version_number,
                    "chunks": _chunk_payload(chunks),
                },
                "requirements": [
                    {
                        "requirement_id": requirement.requirement_id,
                        "title": requirement.title,
                        "description": requirement.description,
                        "category": requirement.category.value,
                        "priority": requirement.priority.value,
                        "source_text": requirement.source_text,
                    }
                    for requirement in sorted(requirements, key=lambda item: item.requirement_id)
                ],
            },
        )

    async def _generate_json(self, *, system_instruction: str, user_payload: dict[str, Any]) -> str:
        try:
            import google.generativeai as genai
        except ImportError:
            raise_error(
                503,
                "AI_PROVIDER_UNAVAILABLE",
                "Gemini dependencies are not installed. Install backend requirements and retry.",
            )

        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                self.model_name,
                system_instruction=system_instruction,
                generation_config={
                    "temperature": 0.0,
                    "response_mime_type": "application/json",
                },
            )
            response = await asyncio.to_thread(
                model.generate_content,
                json.dumps(user_payload, ensure_ascii=False),
                request_options={"timeout": self.timeout_seconds},
            )
            text = getattr(response, "text", None)
        except Exception:
            raise_error(
                503,
                "AI_PROVIDER_UNAVAILABLE",
                "Gemini request failed. Check GEMINI_API_KEY, network access, and provider availability.",
            )

        if not text or not text.strip():
            raise_error(
                502,
                "INVALID_AI_RESPONSE",
                "Gemini returned an empty response.",
            )
        return _strip_json_fence(text.strip())


class UnconfiguredNetworkProvider(RequirementExtractionProvider):
    """Placeholder for real network providers until API credentials are configured."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name

    async def extract_requirements(
        self,
        *,
        guideline_version: GuidelineVersion,
        chunks: list[DocumentChunk],
        repair_prompt: str | None = None,
    ) -> str:
        raise_error(
            503,
            "AI_PROVIDER_UNAVAILABLE",
            (
                f"AI_PROVIDER={self.provider_name} is not configured for live calls in this phase. "
                "Use AI_PROVIDER=mock for deterministic offline extraction."
            ),
        )


class UnconfiguredEvidenceProvider(EvidenceMappingProvider):
    """Placeholder for live evidence providers until credentials are configured."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name

    async def map_evidence(
        self,
        *,
        application_version: ApplicationVersion,
        requirements: list[Requirement],
        chunks: list[DocumentChunk],
        repair_prompt: str | None = None,
    ) -> str:
        raise_error(
            503,
            "AI_PROVIDER_UNAVAILABLE",
            (
                f"AI_PROVIDER={self.provider_name} is not configured for live calls in this phase. "
                "Use AI_PROVIDER=mock for deterministic offline evidence mapping."
            ),
        )


def get_requirement_provider(settings: Settings) -> RequirementExtractionProvider:
    """Return the configured requirement extraction provider."""
    if settings.ai_provider == AIProvider.MOCK:
        return MockRequirementProvider()
    if settings.ai_provider == AIProvider.GEMINI:
        _validate_provider_keys(settings)
        return GeminiProvider(settings)
    return UnconfiguredNetworkProvider(settings.ai_provider.value)


def get_evidence_provider(settings: Settings) -> EvidenceMappingProvider:
    """Return the configured evidence mapping provider."""
    if settings.ai_provider == AIProvider.MOCK:
        return MockEvidenceProvider()
    if settings.ai_provider == AIProvider.GEMINI:
        _validate_provider_keys(settings)
        return GeminiProvider(settings)
    return UnconfiguredEvidenceProvider(settings.ai_provider.value)


def _validate_provider_keys(settings: Settings) -> None:
    try:
        settings.validate_ai_keys()
    except ValueError as exc:
        raise_error(503, "AI_PROVIDER_UNAVAILABLE", str(exc))


def _chunk_payload(chunks: list[DocumentChunk]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "page": chunk.page_number,
            "section": chunk.section_heading,
            "text": chunk.text,
        }
        for chunk in sorted(chunks, key=lambda item: item.chunk_index)
    ]


def _strip_json_fence(text: str) -> str:
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else text


def classify_priority(text: str) -> RequirementPriority | None:
    """Classify requirement priority from deterministic keyword cues."""
    lowered = text.lower()
    if any(cue in lowered for cue in MANDATORY_CUES):
        return RequirementPriority.MANDATORY
    if any(cue in lowered for cue in RECOMMENDED_CUES):
        return RequirementPriority.RECOMMENDED
    return None


def infer_category(text: str) -> str:
    """Infer a broad requirement category from stable keyword cues."""
    lowered = text.lower()
    category_keywords: list[tuple[RequirementCategory, tuple[str, ...]]] = [
        (RequirementCategory.ELIGIBILITY, ("eligib", "nonprofit", "501", "applicant")),
        (RequirementCategory.REQUIRED_DOCUMENTS, ("attach", "appendix", "document", "letter", "certificate")),
        (RequirementCategory.BUDGET, ("budget", "cost", "financial", "match", "funds")),
        (RequirementCategory.TIMELINE, ("timeline", "schedule", "milestone", "month", "date")),
        (RequirementCategory.OBJECTIVES, ("objective", "outcome", "measure", "indicator", "impact")),
        (RequirementCategory.PROJECT_DESCRIPTION, ("project description", "work plan", "activities")),
        (RequirementCategory.ORGANIZATION_INFORMATION, ("organization", "staff", "governance")),
        (RequirementCategory.EVALUATION_CRITERIA, ("evaluation", "score", "criteria")),
        (RequirementCategory.SUBMISSION_REQUIREMENTS, ("submit", "deadline", "portal")),
        (RequirementCategory.FORMATTING_REQUIREMENTS, ("page limit", "font", "format", "margin")),
    ]
    for category, keywords in category_keywords:
        if any(keyword in lowered for keyword in keywords):
            return category.value
    return RequirementCategory.OTHER.value


def _requirement_sentences(text: str) -> list[str]:
    """Split chunk text into requirement-like sentences without randomness."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _title_from_sentence(sentence: str) -> str:
    """Create a concise deterministic title."""
    cleaned = re.sub(r"^(applicants?|the application|application)\s+", "", sentence, flags=re.I)
    words = re.findall(r"[A-Za-z0-9$%()/-]+", cleaned)
    title = " ".join(words[:7]).strip()
    if not title:
        title = "Requirement"
    return title[:1].upper() + title[1:255]


def _is_heading_only_chunk(chunk: DocumentChunk) -> bool:
    """Avoid treating section headings such as Required Documents as requirements."""
    text = re.sub(r"\s+", " ", chunk.text).strip()
    heading = re.sub(r"\s+", " ", chunk.section_heading or "").strip()
    if text and heading and text == heading and len(text.split()) <= 6:
        return True
    if text.endswith((".", "!", "?")):
        return False
    words = text.split()
    if not words or len(words) > 6:
        return False
    return all(word[:1].isupper() for word in words if word[:1].isalpha())


def _map_one_requirement(
    requirement: Requirement,
    application_version: ApplicationVersion,
    chunks: list[DocumentChunk],
) -> dict:
    """Map one requirement using deterministic lexical evidence matching."""
    text = f"{requirement.title} {requirement.description} {requirement.source_text or ''}"
    lowered = text.lower()
    matches = _rank_chunks(text, chunks)
    best = matches[0][1] if matches else None
    second = matches[1][1] if len(matches) > 1 else None

    if _has_contradiction(best, second):
        return _mapping_with_evidence(
            requirement,
            EvidenceStatus.CONTRADICTORY,
            0.72,
            best,
            application_version,
            "The application contains conflicting passages for this requirement.",
            ["Resolve the contradictory application statements."],
            contradictory_evidence=[
                _citation_dict(best, application_version),
                _citation_dict(second, application_version),
            ],
        )

    if best is None:
        return _missing_mapping(requirement, "No relevant application evidence was found.")

    best_text = best.text.lower()
    if _looks_ambiguous(lowered, best_text):
        return _mapping_with_evidence(
            requirement,
            EvidenceStatus.AMBIGUOUS,
            0.48,
            best,
            application_version,
            "Potentially relevant evidence exists, but it is not specific enough to verify the requirement.",
            [_missing_phrase(requirement)],
        )

    if _looks_partial(lowered, best_text):
        return _mapping_with_evidence(
            requirement,
            EvidenceStatus.PARTIALLY_SUPPORTED,
            0.62,
            best,
            application_version,
            "The application addresses part of the requirement but important detail is missing.",
            [_missing_phrase(requirement)],
        )

    return _mapping_with_evidence(
        requirement,
        EvidenceStatus.SUPPORTED,
        0.88,
        best,
        application_version,
        "The cited application passage directly addresses the requirement.",
        [],
    )


def _rank_chunks(text: str, chunks: list[DocumentChunk]) -> list[tuple[int, DocumentChunk]]:
    words = _meaningful_words(text)
    ranked = []
    for chunk in chunks:
        if _is_heading_only_chunk(chunk):
            continue
        chunk_words = _meaningful_words(chunk.text)
        score = len(words & chunk_words)
        if score:
            ranked.append((score, chunk))
    return sorted(ranked, key=lambda item: (-item[0], item[1].chunk_index))


def _meaningful_words(text: str) -> set[str]:
    stopwords = {
        "the", "and", "or", "a", "an", "to", "of", "in", "for", "with", "must",
        "shall", "should", "consider", "include", "provide", "applicants",
        "application", "required", "recommended", "be", "is", "are",
    }
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if len(word) > 2 and word not in stopwords
    }


def _looks_partial(requirement_text: str, evidence_text: str) -> bool:
    return (
        ("detailed" in requirement_text and "detailed" not in evidence_text)
        or ("measurable" in requirement_text and not re.search(r"\d|percent|%|target|indicator", evidence_text))
        or ("breakdown" in requirement_text and "breakdown" not in evidence_text)
    )


def _looks_ambiguous(requirement_text: str, evidence_text: str) -> bool:
    ambiguity_words = {"relevant", "appropriate", "adequate", "positive", "significant"}
    if requirement_text and any(word in evidence_text for word in ambiguity_words):
        has_specific_number = bool(re.search(r"\d|percent|%|year|month", evidence_text))
        return not has_specific_number
    return False


def _has_contradiction(first: DocumentChunk | None, second: DocumentChunk | None) -> bool:
    if first is None or second is None:
        return False
    combined = f"{first.text.lower()} {second.text.lower()}"
    has_negation = any(term in combined for term in ("not ", " no ", "without", "will not"))
    has_positive = any(term in combined for term in ("will ", "does ", "has ", "include", "provide"))
    return has_negation and has_positive


def _missing_mapping(requirement: Requirement, explanation: str) -> dict:
    return {
        "requirement_id": requirement.requirement_id,
        "status": EvidenceStatus.MISSING.value,
        "confidence": 0.2,
        "evidence_text": None,
        "source": None,
        "explanation": explanation,
        "missing_items": [_missing_phrase(requirement)],
    }


def _mapping_with_evidence(
    requirement: Requirement,
    status: EvidenceStatus,
    confidence: float,
    chunk: DocumentChunk,
    application_version: ApplicationVersion,
    explanation: str,
    missing_items: list[str],
    contradictory_evidence: list[dict] | None = None,
) -> dict:
    return {
        "requirement_id": requirement.requirement_id,
        "status": status.value,
        "confidence": confidence,
        "evidence_text": chunk.text,
        "source": _citation_dict(chunk, application_version),
        "explanation": explanation,
        "missing_items": missing_items,
        "contradictory_evidence": contradictory_evidence,
    }


def _citation_dict(chunk: DocumentChunk, application_version: ApplicationVersion) -> dict:
    return {
        "chunk_id": chunk.id,
        "document": application_version.filename,
        "version": application_version.version_number,
        "page": chunk.page_number,
        "section": chunk.section_heading,
    }


def _missing_phrase(requirement: Requirement) -> str:
    return f"Provide verifiable application evidence for: {requirement.title}."
