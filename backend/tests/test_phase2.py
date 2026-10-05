"""
Comprehensive tests for Phase 2: Database Models.
Validates all 13 SQLAlchemy 2.x models, relationships, foreign keys,
unique constraints, check constraints, cascading deletes, enums,
effective status calculation, and assessment history preservation.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base
from app.models import (
    Application,
    ApplicationVersion,
    Assessment,
    AssessmentItem,
    AssessmentStatus,
    ClarificationQuestion,
    DocumentChunk,
    DocumentType,
    EvidenceMapping,
    EvidenceSourceType,
    EvidenceStatus,
    GrantGuideline,
    GuidelineVersion,
    OverallReviewStatus,
    Project,
    QuestionState,
    Requirement,
    RequirementCategory,
    RequirementPriority,
    ReviewAction,
    SupportingDocument,
    SupportingDocumentStatus,
    UserReview,
)


# ===================================================================
# 1. Metadata and Table Registration
# ===================================================================
class TestModelRegistration:
    """Verify all 13 models are properly registered in Base metadata."""

    def test_all_13_tables_registered(self):
        """Base.metadata must register all 13 required database tables."""
        expected_tables = {
            "projects",
            "grant_guidelines",
            "guideline_versions",
            "applications",
            "application_versions",
            "supporting_documents",
            "document_chunks",
            "requirements",
            "evidence_mappings",
            "clarification_questions",
            "assessments",
            "assessment_items",
            "user_reviews",
        }
        registered_tables = set(Base.metadata.tables.keys())
        assert expected_tables.issubset(registered_tables), (
            f"Missing tables: {expected_tables - registered_tables}"
        )
        assert len(expected_tables) == 13


# ===================================================================
# 2. Project Model Tests
# ===================================================================
class TestProjectModel:
    """Test the Project root model."""

    @pytest.mark.asyncio
    async def test_create_project_defaults(self, db_session: AsyncSession):
        """Creating a project should auto-generate UUID and timestamps."""
        project = Project(name="Renewable Energy Grant Review")
        db_session.add(project)
        await db_session.commit()

        res = await db_session.execute(select(Project).where(Project.name == "Renewable Energy Grant Review"))
        saved = res.scalar_one()

        assert saved.id is not None
        assert len(saved.id) == 36
        assert saved.created_at is not None
        assert saved.updated_at is not None
        assert saved.description is None
        assert "Renewable Energy" in repr(saved)

    @pytest.mark.asyncio
    async def test_create_project_with_description(self, db_session: AsyncSession):
        """Creating a project with custom description."""
        project = Project(
            name="Health Tech Innovation",
            description="Grant review for 2026 NIH medical devices RFP",
        )
        db_session.add(project)
        await db_session.commit()

        res = await db_session.execute(select(Project).where(Project.id == project.id))
        saved = res.scalar_one()
        assert saved.description == "Grant review for 2026 NIH medical devices RFP"


# ===================================================================
# 3. Guideline and Versioning Tests
# ===================================================================
class TestGuidelineModels:
    """Test GrantGuideline and GuidelineVersion models."""

    @pytest.mark.asyncio
    async def test_create_guideline_and_version(self, db_session: AsyncSession):
        """Guideline and GuidelineVersion creation and linking."""
        project = Project(name="Guideline Test Project")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id, name="DOE Guidelines 2026")
        db_session.add(guideline)
        await db_session.flush()

        v1 = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="doe_guidelines_v1.pdf",
            file_path="/uploads/doe_v1.pdf",
            file_hash="hash_sha256_doe_v1",
            file_size_bytes=1048576,
            mime_type="application/pdf",
            total_pages=15,
            total_chunks=30,
            raw_text="Extracted text from DOE guideline",
        )
        db_session.add(v1)
        await db_session.commit()

        res = await db_session.execute(select(GrantGuideline).where(GrantGuideline.id == guideline.id))
        saved_guideline = res.scalar_one()

        assert len(saved_guideline.versions) == 1
        assert saved_guideline.current_version.version_number == 1
        assert saved_guideline.current_version.filename == "doe_guidelines_v1.pdf"

    @pytest.mark.asyncio
    async def test_multiple_versions_ordered(self, db_session: AsyncSession):
        """Multiple versions should be ordered by version_number."""
        project = Project(name="Multi-version Project")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        v1 = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="guideline_v1.pdf",
            file_path="/path/v1",
            file_hash="hash1",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        v2 = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=2,
            filename="guideline_v2.pdf",
            file_path="/path/v2",
            file_hash="hash2",
            file_size_bytes=150,
            mime_type="application/pdf",
        )
        db_session.add_all([v1, v2])
        await db_session.commit()

        res = await db_session.execute(select(GrantGuideline).where(GrantGuideline.id == guideline.id))
        saved_guideline = res.scalar_one()

        assert len(saved_guideline.versions) == 2
        assert saved_guideline.versions[0].version_number == 1
        assert saved_guideline.versions[1].version_number == 2
        assert saved_guideline.current_version.version_number == 2

    @pytest.mark.asyncio
    async def test_duplicate_version_number_rejected(self, db_session: AsyncSession):
        """GuidelineVersion version_number must be unique per guideline."""
        project = Project(name="Duplicate Version Test")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        v1a = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="file_a.pdf",
            file_path="/path/a",
            file_hash="hash_a",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(v1a)
        await db_session.flush()

        v1b = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,  # Duplicate version 1
            filename="file_b.pdf",
            file_path="/path/b",
            file_hash="hash_b",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(v1b)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_duplicate_file_hash_rejected(self, db_session: AsyncSession):
        """GuidelineVersion file_hash must be unique per guideline (§5 duplicate upload)."""
        project = Project(name="Duplicate Hash Test")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        v1 = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="file1.pdf",
            file_path="/path/1",
            file_hash="identical_sha256",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(v1)
        await db_session.flush()

        v2 = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=2,
            filename="file2_renamed.pdf",
            file_path="/path/2",
            file_hash="identical_sha256",  # Same file hash
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(v2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


# ===================================================================
# 4. Application and Versioning Tests
# ===================================================================
class TestApplicationModels:
    """Test Application and ApplicationVersion models."""

    @pytest.mark.asyncio
    async def test_create_application_and_version(self, db_session: AsyncSession):
        """Application and ApplicationVersion creation and linking."""
        project = Project(name="App Version Test")
        db_session.add(project)
        await db_session.flush()

        app = Application(project_id=project.id, name="Grant Draft Application")
        db_session.add(app)
        await db_session.flush()

        v1 = ApplicationVersion(
            application_id=app.id,
            version_number=1,
            filename="draft_v1.docx",
            file_path="/uploads/draft_v1.docx",
            file_hash="app_hash_v1",
            file_size_bytes=524288,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            total_chunks=12,
            raw_text="Full text of draft application",
        )
        db_session.add(v1)
        await db_session.commit()

        res = await db_session.execute(select(Application).where(Application.id == app.id))
        saved_app = res.scalar_one()

        assert len(saved_app.versions) == 1
        assert saved_app.current_version.version_number == 1
        assert saved_app.current_version.filename == "draft_v1.docx"

    @pytest.mark.asyncio
    async def test_duplicate_application_hash_rejected(self, db_session: AsyncSession):
        """Duplicate application upload with same hash should be rejected (§5)."""
        project = Project(name="App Duplicate Hash")
        db_session.add(project)
        await db_session.flush()

        app = Application(project_id=project.id)
        db_session.add(app)
        await db_session.flush()

        v1 = ApplicationVersion(
            application_id=app.id,
            version_number=1,
            filename="app_v1.pdf",
            file_path="/p1",
            file_hash="app_sha256_same",
            file_size_bytes=200,
            mime_type="application/pdf",
        )
        db_session.add(v1)
        await db_session.flush()

        v2 = ApplicationVersion(
            application_id=app.id,
            version_number=2,
            filename="app_v2.pdf",
            file_path="/p2",
            file_hash="app_sha256_same",
            file_size_bytes=200,
            mime_type="application/pdf",
        )
        db_session.add(v2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


# ===================================================================
# 5. DocumentChunk Model Tests
# ===================================================================
class TestDocumentChunkModel:
    """Test DocumentChunk model for structured text chunking (§5)."""

    @pytest.mark.asyncio
    async def test_guideline_chunk_provenance(self, db_session: AsyncSession):
        """DocumentChunk stores detailed page, section, and offset provenance."""
        project = Project(name="Chunk Test")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        gv = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="guide.pdf",
            file_path="/path",
            file_hash="h1",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(gv)
        await db_session.flush()

        chunk = DocumentChunk(
            guideline_version_id=gv.id,
            document_type=DocumentType.GUIDELINE,
            chunk_index=3,
            text="Applicants must have at least 3 years of audited financials.",
            page_number=4,
            section_heading="Financial Eligibility",
            paragraph_index=2,
            char_start=1520,
            char_end=1583,
            token_count=12,
        )
        db_session.add(chunk)
        await db_session.commit()

        res = await db_session.execute(select(DocumentChunk).where(DocumentChunk.id == chunk.id))
        saved = res.scalar_one()

        assert saved.document_type == DocumentType.GUIDELINE
        assert saved.page_number == 4
        assert saved.section_heading == "Financial Eligibility"
        assert saved.char_start == 1520
        assert saved.token_count == 12
        assert "Financial Eligibility" in repr(saved) or "guideline" in repr(saved)

    @pytest.mark.asyncio
    async def test_chunk_check_constraint_enforced(self, db_session: AsyncSession):
        """Chunk cannot have both guideline and application IDs or neither."""
        # Test case: neither guideline nor application ID provided
        invalid_chunk = DocumentChunk(
            document_type=DocumentType.GUIDELINE,
            chunk_index=0,
            text="Invalid orphan chunk",
        )
        db_session.add(invalid_chunk)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


# ===================================================================
# 6. Requirement Model Tests
# ===================================================================
class TestRequirementModel:
    """Test Requirement model (§6, §7)."""

    @pytest.mark.asyncio
    async def test_create_requirement_with_provenance(self, db_session: AsyncSession):
        """Requirement stores verbatim excerpt, category, and priority."""
        project = Project(name="Requirement Test")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        gv = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="g.pdf",
            file_path="/p",
            file_hash="ghash",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(gv)
        await db_session.flush()

        req = Requirement(
            guideline_version_id=gv.id,
            requirement_id="REQ-001",
            title="Applicant Track Record",
            description="Applicant must demonstrate at least 3 years operating history.",
            category=RequirementCategory.ELIGIBILITY,
            priority=RequirementPriority.MANDATORY,
            source_document="g.pdf",
            source_page=2,
            source_section="Eligibility Criteria",
            source_text="The applicant organization must demonstrate a minimum of 3 years operating history.",
            is_manually_added=False,
            priority_flagged_for_review=False,
        )
        db_session.add(req)
        await db_session.commit()

        res = await db_session.execute(select(Requirement).where(Requirement.id == req.id))
        saved = res.scalar_one()

        assert saved.requirement_id == "REQ-001"
        assert saved.category == RequirementCategory.ELIGIBILITY
        assert saved.priority == RequirementPriority.MANDATORY
        assert saved.source_page == 2
        assert "REQ-001" in repr(saved)

    @pytest.mark.asyncio
    async def test_duplicate_requirement_id_in_same_guideline_rejected(self, db_session: AsyncSession):
        """Requirement identifier must be unique per guideline version."""
        project = Project(name="Req Uniqueness")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        gv = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="g.pdf",
            file_path="/p",
            file_hash="ghash",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(gv)
        await db_session.flush()

        r1 = Requirement(
            guideline_version_id=gv.id,
            requirement_id="REQ-001",
            title="Budget Plan",
            description="Detailed budget required",
            category=RequirementCategory.BUDGET,
            priority=RequirementPriority.MANDATORY,
        )
        db_session.add(r1)
        await db_session.flush()

        r2 = Requirement(
            guideline_version_id=gv.id,
            requirement_id="REQ-001",  # Duplicate REQ-001 in same guideline version
            title="Another Budget Requirement",
            description="Duplicate ID description",
            category=RequirementCategory.BUDGET,
            priority=RequirementPriority.RECOMMENDED,
        )
        db_session.add(r2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


# ===================================================================
# 7. SupportingDocument Model Tests
# ===================================================================
class TestSupportingDocumentModel:
    """Test SupportingDocument model (§15)."""

    @pytest.mark.asyncio
    async def test_create_supporting_document(self, db_session: AsyncSession):
        """Supporting document tracking metadata with related requirements."""
        project = Project(name="Supporting Doc Test")
        db_session.add(project)
        await db_session.flush()

        doc = SupportingDocument(
            project_id=project.id,
            name="IRS 501(c)(3) Determination Letter",
            document_type="Legal / Tax",
            status=SupportingDocumentStatus.PROVIDED,
            related_requirement_ids=["REQ-001", "REQ-004"],
            notes="Tax exempt verification letter on file.",
        )
        db_session.add(doc)
        await db_session.commit()

        res = await db_session.execute(select(SupportingDocument).where(SupportingDocument.id == doc.id))
        saved = res.scalar_one()

        assert saved.status == SupportingDocumentStatus.PROVIDED
        assert saved.related_requirement_ids == ["REQ-001", "REQ-004"]
        assert saved.document_type == "Legal / Tax"
        assert "501(c)(3)" in repr(saved)

    @pytest.mark.asyncio
    async def test_default_status_is_missing(self, db_session: AsyncSession):
        """Default supporting document status should be MISSING."""
        project = Project(name="Supp Doc Default")
        db_session.add(project)
        await db_session.flush()

        doc = SupportingDocument(project_id=project.id, name="Letter of Support")
        db_session.add(doc)
        await db_session.commit()

        res = await db_session.execute(select(SupportingDocument).where(SupportingDocument.id == doc.id))
        saved = res.scalar_one()
        assert saved.status == SupportingDocumentStatus.MISSING
        assert saved.related_requirement_ids == []


# ===================================================================
# 8. EvidenceMapping and UserReview Model Tests
# ===================================================================
class TestEvidenceAndReviewModels:
    """Test EvidenceMapping and UserReview models (§8, §17)."""

    @pytest.mark.asyncio
    async def test_evidence_mapping_effective_status_without_review(self, db_session: AsyncSession):
        """Without human review, effective status equals AI status."""
        project = Project(name="Evidence Test")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        gv = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="g.pdf",
            file_path="/p",
            file_hash="gh1",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(gv)
        await db_session.flush()

        req = Requirement(
            guideline_version_id=gv.id,
            requirement_id="REQ-001",
            title="Timeline",
            description="12-month work plan",
            category=RequirementCategory.TIMELINE,
            priority=RequirementPriority.MANDATORY,
        )
        db_session.add(req)
        await db_session.flush()

        mapping = EvidenceMapping(
            project_id=project.id,
            requirement_id=req.id,
            status=EvidenceStatus.PARTIALLY_SUPPORTED,
            confidence=0.75,
            evidence_text="Project will commence in Q1.",
            explanation="Commencement given but no quarterly breakdown.",
            missing_items=["Quarterly milestone schedule", "Risk mitigation plan"],
            source_type=EvidenceSourceType.APPLICATION,
        )
        db_session.add(mapping)
        await db_session.commit()

        res = await db_session.execute(select(EvidenceMapping).where(EvidenceMapping.id == mapping.id))
        saved = res.scalar_one()

        assert saved.status == EvidenceStatus.PARTIALLY_SUPPORTED
        assert saved.effective_status == EvidenceStatus.PARTIALLY_SUPPORTED
        assert saved.missing_items == ["Quarterly milestone schedule", "Risk mitigation plan"]
        assert saved.user_review is None

    @pytest.mark.asyncio
    async def test_user_review_confirm_action(self, db_session: AsyncSession):
        """User review CONFIRM retains the AI status as effective status."""
        project = Project(name="Review Confirm Test")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        gv = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="g.pdf",
            file_path="/p",
            file_hash="gh2",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(gv)
        await db_session.flush()

        req = Requirement(
            guideline_version_id=gv.id,
            requirement_id="REQ-002",
            title="Budget Total",
            description="Total budget capped at $500k",
            category=RequirementCategory.BUDGET,
            priority=RequirementPriority.MANDATORY,
        )
        db_session.add(req)
        await db_session.flush()

        mapping = EvidenceMapping(
            project_id=project.id,
            requirement_id=req.id,
            status=EvidenceStatus.SUPPORTED,
            confidence=0.92,
            evidence_text="Total requested budget is $450,000.",
            explanation="Within allowable cap.",
        )
        db_session.add(mapping)
        await db_session.flush()

        review = UserReview(
            evidence_mapping_id=mapping.id,
            action=ReviewAction.CONFIRMED,
            reviewer_name="Dr. Smith",
            notes="Checked against table 4.1",
        )
        db_session.add(review)
        await db_session.commit()

        res = await db_session.execute(select(EvidenceMapping).where(EvidenceMapping.id == mapping.id))
        saved = res.scalar_one()

        assert saved.status == EvidenceStatus.SUPPORTED
        assert saved.user_review.action == ReviewAction.CONFIRMED
        assert saved.effective_status == EvidenceStatus.SUPPORTED

    @pytest.mark.asyncio
    async def test_user_review_reject_action(self, db_session: AsyncSession):
        """User review REJECT sets effective status to REJECTED (§17)."""
        project = Project(name="Review Reject Test")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        gv = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="g.pdf",
            file_path="/p",
            file_hash="gh3",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(gv)
        await db_session.flush()

        req = Requirement(
            guideline_version_id=gv.id,
            requirement_id="REQ-003",
            title="Partnership MoU",
            description="MoU with community partner",
            category=RequirementCategory.REQUIRED_DOCUMENTS,
            priority=RequirementPriority.MANDATORY,
        )
        db_session.add(req)
        await db_session.flush()

        mapping = EvidenceMapping(
            project_id=project.id,
            requirement_id=req.id,
            status=EvidenceStatus.SUPPORTED,
            confidence=0.6,
            evidence_text="We have a verbal agreement with ABC Corp.",
            explanation="Verbal agreement cited.",
        )
        db_session.add(mapping)
        await db_session.flush()

        # Reviewer rejects the AI mapping because verbal agreement is not an MoU
        review = UserReview(
            evidence_mapping_id=mapping.id,
            action=ReviewAction.REJECTED,
            reviewer_name="Grant Officer",
            notes="Verbal agreement is not an executed MoU.",
        )
        db_session.add(review)
        await db_session.commit()

        res = await db_session.execute(select(EvidenceMapping).where(EvidenceMapping.id == mapping.id))
        saved = res.scalar_one()

        # Original AI status is preserved
        assert saved.status == EvidenceStatus.SUPPORTED
        # Effective status used in scoring is REJECTED
        assert saved.effective_status == EvidenceStatus.REJECTED

    @pytest.mark.asyncio
    async def test_user_review_edit_action(self, db_session: AsyncSession):
        """User review EDIT overrides status, evidence, and explanation (§17)."""
        project = Project(name="Review Edit Test")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        gv = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="g.pdf",
            file_path="/p",
            file_hash="gh4",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(gv)
        await db_session.flush()

        req = Requirement(
            guideline_version_id=gv.id,
            requirement_id="REQ-004",
            title="Outcomes",
            description="Measurable quantitative outcomes",
            category=RequirementCategory.OBJECTIVES,
            priority=RequirementPriority.MANDATORY,
        )
        db_session.add(req)
        await db_session.flush()

        mapping = EvidenceMapping(
            project_id=project.id,
            requirement_id=req.id,
            status=EvidenceStatus.AMBIGUOUS,
            confidence=0.5,
            evidence_text="We expect positive changes.",
            explanation="Unclear if measurable.",
        )
        db_session.add(mapping)
        await db_session.flush()

        review = UserReview(
            evidence_mapping_id=mapping.id,
            action=ReviewAction.EDITED,
            reviewed_status=EvidenceStatus.SUPPORTED,
            reviewed_evidence_text="Section 3.2 lists: 200 youth trained, 85% placement rate.",
            reviewed_explanation="Reviewer located measurable targets in section 3.2.",
            reviewer_name="Senior Reviewer",
        )
        db_session.add(review)
        await db_session.commit()

        res = await db_session.execute(select(EvidenceMapping).where(EvidenceMapping.id == mapping.id))
        saved = res.scalar_one()

        # AI values preserved
        assert saved.status == EvidenceStatus.AMBIGUOUS
        assert saved.evidence_text == "We expect positive changes."
        # Effective values updated
        assert saved.effective_status == EvidenceStatus.SUPPORTED
        assert "200 youth trained" in saved.effective_evidence_text
        assert "section 3.2" in saved.effective_explanation


# ===================================================================
# 9. ClarificationQuestion Model Tests
# ===================================================================
class TestClarificationQuestionModel:
    """Test ClarificationQuestion model (§14)."""

    @pytest.mark.asyncio
    async def test_question_lifecycle(self, db_session: AsyncSession):
        """Clarification questions track states: OPEN, ANSWERED, DISMISSED."""
        project = Project(name="Question Test")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        gv = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="g.pdf",
            file_path="/p",
            file_hash="gh5",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(gv)
        await db_session.flush()

        req = Requirement(
            guideline_version_id=gv.id,
            requirement_id="REQ-005",
            title="Indirect Cost Rate",
            description="Specify indirect cost rate agreement",
            category=RequirementCategory.BUDGET,
            priority=RequirementPriority.MANDATORY,
        )
        db_session.add(req)
        await db_session.flush()

        q = ClarificationQuestion(
            project_id=project.id,
            requirement_id=req.id,
            question_text="Does the applicant have a federally negotiated indirect cost rate agreement?",
            state=QuestionState.OPEN,
        )
        db_session.add(q)
        await db_session.commit()

        res = await db_session.execute(select(ClarificationQuestion).where(ClarificationQuestion.id == q.id))
        saved_q = res.scalar_one()
        assert saved_q.state == QuestionState.OPEN
        assert saved_q.answer_text is None

        # User answers the question
        saved_q.answer_text = "Yes, NICRA agreement dated June 2025 at 15% rate."
        saved_q.state = QuestionState.ANSWERED
        await db_session.commit()

        res2 = await db_session.execute(select(ClarificationQuestion).where(ClarificationQuestion.id == q.id))
        updated_q = res2.scalar_one()
        assert updated_q.state == QuestionState.ANSWERED
        assert "NICRA agreement" in updated_q.answer_text


# ===================================================================
# 10. Assessment and AssessmentItem Model Tests
# ===================================================================
class TestAssessmentModels:
    """Test Assessment and AssessmentItem models (§16, §18, §19)."""

    @pytest.mark.asyncio
    async def test_create_assessment_with_scores_and_items(self, db_session: AsyncSession):
        """Assessment records complete score snapshot, counts, and items."""
        project = Project(name="Assessment Scoring Test")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        db_session.add(guideline)
        await db_session.flush()

        gv = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="g.pdf",
            file_path="/p",
            file_hash="gh6",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(gv)
        await db_session.flush()

        app = Application(project_id=project.id)
        db_session.add(app)
        await db_session.flush()

        av = ApplicationVersion(
            application_id=app.id,
            version_number=1,
            filename="a.pdf",
            file_path="/pa",
            file_hash="ah1",
            file_size_bytes=100,
            mime_type="application/pdf",
        )
        db_session.add(av)
        await db_session.flush()

        req = Requirement(
            guideline_version_id=gv.id,
            requirement_id="REQ-001",
            title="Eligibility",
            description="Eligibility requirement",
            category=RequirementCategory.ELIGIBILITY,
            priority=RequirementPriority.MANDATORY,
        )
        db_session.add(req)
        await db_session.flush()

        assessment = Assessment(
            project_id=project.id,
            guideline_version_id=gv.id,
            application_version_id=av.id,
            assessment_status=AssessmentStatus.COMPLETED,
            overall_status=OverallReviewStatus.NOT_READY,
            mandatory_completeness=0.75,
            recommended_completeness=1.0,
            overall_completeness=0.833,
            mandatory_supported_count=7,
            mandatory_partial_count=1,
            mandatory_missing_count=2,
            mandatory_total_count=10,
            recommended_supported_count=5,
            recommended_total_count=5,
            critical_missing_items=[
                {"id": "REQ-002", "title": "Personnel Breakdown", "missing": ["Staff CVs"]},
                {"id": "REQ-007", "title": "Audit Report", "missing": ["2024 Audit"]},
            ],
            requirements_snapshot=[
                {"id": "REQ-001", "title": "Eligibility", "priority": "mandatory"},
            ],
            is_stale=False,
        )
        db_session.add(assessment)
        await db_session.flush()

        # Add AssessmentItem to freeze historical requirement result
        item = AssessmentItem(
            assessment_id=assessment.id,
            requirement_id=req.id,
            requirement_identifier="REQ-001",
            requirement_title=req.title,
            requirement_category=req.category,
            requirement_priority=req.priority,
            ai_status=EvidenceStatus.SUPPORTED,
            effective_status=EvidenceStatus.SUPPORTED,
            points=1.0,
            in_denominator=True,
            evidence_text="Applicant is fully eligible.",
            explanation="Meets all criteria.",
        )
        db_session.add(item)
        await db_session.commit()

        res = await db_session.execute(select(Assessment).where(Assessment.id == assessment.id))
        saved = res.scalar_one()

        assert saved.overall_status == OverallReviewStatus.NOT_READY
        assert saved.mandatory_completeness == 0.75
        assert saved.mandatory_missing_count == 2
        assert len(saved.critical_missing_items) == 2
        assert len(saved.items) == 1
        assert saved.items[0].points == 1.0
        assert saved.items[0].effective_status == EvidenceStatus.SUPPORTED
        assert saved.is_stale is False

    @pytest.mark.asyncio
    async def test_staleness_flag_and_reason(self, db_session: AsyncSession):
        """Staleness can be flagged with a descriptive reason (§19)."""
        project = Project(name="Staleness Test")
        db_session.add(project)
        await db_session.flush()

        assessment = Assessment(
            project_id=project.id,
            assessment_status=AssessmentStatus.COMPLETED,
            overall_status=OverallReviewStatus.READY_FOR_REVIEW,
            overall_completeness=1.0,
            is_stale=True,
            stale_reason="New application version uploaded (v2)",
        )
        db_session.add(assessment)
        await db_session.commit()

        res = await db_session.execute(select(Assessment).where(Assessment.id == assessment.id))
        saved = res.scalar_one()

        assert saved.is_stale is True
        assert saved.stale_reason == "New application version uploaded (v2)"


# ===================================================================
# 11. Foreign Key Cascades Tests
# ===================================================================
class TestCascadingDeletions:
    """Verify that deleting a Project or parent model cleanly cascades to child records."""

    @pytest.mark.asyncio
    async def test_project_deletion_cascades_to_all_children(self, db_session: AsyncSession):
        """Deleting a Project must cascade and delete all associated models."""
        project = Project(name="Cascade Delete Test")
        db_session.add(project)
        await db_session.flush()

        guideline = GrantGuideline(project_id=project.id)
        app = Application(project_id=project.id)
        sdoc = SupportingDocument(project_id=project.id, name="Cert")
        db_session.add_all([guideline, app, sdoc])
        await db_session.flush()

        gv = GuidelineVersion(
            guideline_id=guideline.id,
            version_number=1,
            filename="g.pdf",
            file_path="/p",
            file_hash="h1",
            file_size_bytes=10,
            mime_type="application/pdf",
        )
        db_session.add(gv)
        await db_session.flush()

        req = Requirement(
            guideline_version_id=gv.id,
            requirement_id="REQ-001",
            title="T",
            description="D",
            category=RequirementCategory.OTHER,
            priority=RequirementPriority.MANDATORY,
        )
        db_session.add(req)
        await db_session.flush()

        ev = EvidenceMapping(
            project_id=project.id,
            requirement_id=req.id,
            status=EvidenceStatus.MISSING,
        )
        q = ClarificationQuestion(
            project_id=project.id,
            requirement_id=req.id,
            question_text="Q?",
        )
        assess = Assessment(
            project_id=project.id,
            assessment_status=AssessmentStatus.COMPLETED,
        )
        db_session.add_all([ev, q, assess])
        await db_session.commit()

        # Delete the project
        await db_session.delete(project)
        await db_session.commit()

        # All child tables should now have zero records for this project
        g_check = await db_session.execute(select(GrantGuideline).where(GrantGuideline.project_id == project.id))
        assert g_check.first() is None

        a_check = await db_session.execute(select(Application).where(Application.project_id == project.id))
        assert a_check.first() is None

        s_check = await db_session.execute(select(SupportingDocument).where(SupportingDocument.project_id == project.id))
        assert s_check.first() is None

        e_check = await db_session.execute(select(EvidenceMapping).where(EvidenceMapping.project_id == project.id))
        assert e_check.first() is None

        q_check = await db_session.execute(select(ClarificationQuestion).where(ClarificationQuestion.project_id == project.id))
        assert q_check.first() is None

        as_check = await db_session.execute(select(Assessment).where(Assessment.project_id == project.id))
        assert as_check.first() is None
