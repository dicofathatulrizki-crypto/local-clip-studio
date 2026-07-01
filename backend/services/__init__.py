"""Application service layer — business logic orchestration.

Modules:
    B5: ProjectService — project lifecycle management (CRUD, archive, restore, duplicate)
"""

from backend.services.project_service import ProjectService

__all__ = [
    "ProjectService",
]
