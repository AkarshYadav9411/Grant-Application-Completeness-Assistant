"""
Enumeration types used across database models.
All stored as VARCHAR strings for PostgreSQL and SQLite compatibility.
"""

from enum import Enum


class RequirementCategory(str, Enum):
    """Categories for grant requirements (§6)."""
    ELIGIBILITY = "eligibility"
    REQUIRED_INFORMATION = "required_information"
    REQUIRED_DOCUMENTS = "required_documents"
    PROJECT_DESCRIPTION = "project_description"
    OBJECTIVES = "objectives"
    BUDGET = "budget"
    TIMELINE = "timeline"
    ORGANIZATION_INFORMATION = "organization_information"
    EVALUATION_CRITERIA = "evaluation_criteria"
    SUBMISSION_REQUIREMENTS = "submission_requirements"
    FORMATTING_REQUIREMENTS = "formatting_requirements"
    OTHER = "other"


class RequirementPriority(str, Enum):
    """Priority classification for requirements (§7)."""
    MANDATORY = "mandatory"
    RECOMMENDED = "recommended"


class EvidenceStatus(str, Enum):
    """Status of evidence mapping for a requirement (§9)."""
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    CONTRADICTORY = "CONTRADICTORY"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REJECTED = "REJECTED"


class AssessmentStatus(str, Enum):
    """Status of an assessment run."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class OverallReviewStatus(str, Enum):
    """Deterministic overall review status (§16)."""
    NOT_READY = "NOT_READY"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"


class ReviewAction(str, Enum):
    """Actions a user can take on an evidence mapping (§17)."""
    CONFIRMED = "confirmed"
    EDITED = "edited"
    REJECTED = "rejected"


class QuestionState(str, Enum):
    """State of a clarification question (§14)."""
    OPEN = "open"
    ANSWERED = "answered"
    DISMISSED = "dismissed"


class SupportingDocumentStatus(str, Enum):
    """Status of a supporting document (§15)."""
    PROVIDED = "provided"
    MISSING = "missing"
    NOT_REQUIRED = "not_required"


class DocumentType(str, Enum):
    """Type of document for text chunking (§5)."""
    GUIDELINE = "guideline"
    APPLICATION = "application"


class EvidenceSourceType(str, Enum):
    """Source type for evidence mapping (§8, §15)."""
    APPLICATION = "application"
    SUPPORTING_DOCUMENT = "supporting_document"

