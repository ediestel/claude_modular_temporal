"""
Stage definitions for Claude Temporal workflows.

Extracts hardcoded stage definitions into configurable templates
that can be customized per project or loaded from external config.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class DevelopmentStage:
    """Configuration for a development stage in a workflow."""
    name: str
    prompt: str
    requires_approval: bool = False
    critical_path: bool = True
    skip_tests: bool = False
    max_tokens: int = 8000
    temperature: float = 0.3


@dataclass
class StageTemplate:
    """
    Template for generating stage prompts.

    Allows customization of prompts with project-specific variables.
    """
    name: str
    prompt_template: str
    requires_approval: bool = False
    critical_path: bool = True
    skip_tests: bool = False
    max_tokens: int = 8000
    temperature: float = 0.3

    def to_stage(self, **kwargs) -> DevelopmentStage:
        """
        Generate a DevelopmentStage with variables substituted.

        Args:
            **kwargs: Variables to substitute in the prompt template

        Returns:
            DevelopmentStage with formatted prompt
        """
        return DevelopmentStage(
            name=self.name,
            prompt=self.prompt_template.format(**kwargs),
            requires_approval=self.requires_approval,
            critical_path=self.critical_path,
            skip_tests=self.skip_tests,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )


# Default LLM Wrapper Development Stages
LLM_WRAPPER_STAGES = [
    StageTemplate(
        name="scaffold",
        prompt_template="""Create a TypeScript LLM wrapper library with:
- Support for OpenAI, Anthropic, and local models
- Type-safe interfaces
- Streaming support
- Error handling and retries
- Cost tracking
Setup project structure in {project_path}""",
        requires_approval=False,
        critical_path=True,
    ),
    StageTemplate(
        name="core-implementation",
        prompt_template="""Implement core wrapper functionality:
- Base LLMClient abstract class
- OpenAI provider implementation
- Anthropic provider implementation
- Unified response format
- Token counting utilities""",
        requires_approval=True,  # Human review before proceeding
        critical_path=True,
    ),
    StageTemplate(
        name="streaming",
        prompt_template="""Add streaming support:
- Server-sent events handling
- Async iterators for streams
- Backpressure handling
- Stream cancellation""",
        requires_approval=False,
        critical_path=True,
    ),
    StageTemplate(
        name="error-handling",
        prompt_template="""Implement robust error handling:
- Custom error classes for different failure types
- Exponential backoff with jitter
- Circuit breaker pattern
- Request timeout handling
- Rate limit detection and retry""",
        requires_approval=False,
        critical_path=False,
    ),
    StageTemplate(
        name="testing",
        prompt_template="""Create comprehensive test suite:
- Unit tests for each provider
- Integration tests with mock APIs
- Streaming tests
- Error handling tests
- Edge case coverage""",
        requires_approval=False,
        critical_path=True,
    ),
    StageTemplate(
        name="documentation",
        prompt_template="""Generate complete documentation:
- README with quick start guide
- API reference for all public methods
- Usage examples for common scenarios
- Migration guides
- TypeScript type documentation""",
        requires_approval=False,
        critical_path=False,
        skip_tests=True,  # Documentation stage doesn't need test validation
    ),
]


# API Development Stages
API_DEVELOPMENT_STAGES = [
    StageTemplate(
        name="scaffold",
        prompt_template="""Create API project structure in {project_path}:
- FastAPI/Express framework setup
- Database models and migrations
- Authentication middleware
- API documentation setup""",
        requires_approval=False,
        critical_path=True,
    ),
    StageTemplate(
        name="endpoints",
        prompt_template="""Implement API endpoints:
- CRUD operations for main resources
- Input validation
- Error responses
- Pagination support""",
        requires_approval=True,
        critical_path=True,
    ),
    StageTemplate(
        name="authentication",
        prompt_template="""Add authentication and authorization:
- JWT token handling
- Role-based access control
- API key management
- Rate limiting""",
        requires_approval=True,
        critical_path=True,
    ),
    StageTemplate(
        name="testing",
        prompt_template="""Create API test suite:
- Unit tests for handlers
- Integration tests for endpoints
- Authentication tests
- Error handling tests""",
        requires_approval=False,
        critical_path=True,
    ),
]


# Frontend Development Stages
FRONTEND_STAGES = [
    StageTemplate(
        name="scaffold",
        prompt_template="""Create frontend project in {project_path}:
- React/Vue/Svelte setup
- Component library integration
- State management setup
- Build configuration""",
        requires_approval=False,
        critical_path=True,
    ),
    StageTemplate(
        name="components",
        prompt_template="""Implement UI components:
- Layout components
- Form components
- Data display components
- Navigation components""",
        requires_approval=False,
        critical_path=True,
    ),
    StageTemplate(
        name="pages",
        prompt_template="""Create application pages:
- Main dashboard
- Detail views
- Forms and editors
- Settings pages""",
        requires_approval=True,
        critical_path=True,
    ),
    StageTemplate(
        name="testing",
        prompt_template="""Add frontend tests:
- Component unit tests
- Integration tests
- Accessibility tests
- Visual regression tests""",
        requires_approval=False,
        critical_path=True,
    ),
]


@dataclass
class StageConfig:
    """
    Configuration for stage management.

    Allows projects to customize which stages to run and their order.
    """
    stages: list[StageTemplate] = field(default_factory=list)
    skip_stages: list[str] = field(default_factory=list)
    custom_prompts: dict[str, str] = field(default_factory=dict)

    def get_stages(self, project_path: str, **kwargs) -> list[DevelopmentStage]:
        """
        Get configured stages with project path substituted.

        Args:
            project_path: Path to substitute in templates
            **kwargs: Additional variables for templates

        Returns:
            List of configured DevelopmentStage instances
        """
        result = []
        for template in self.stages:
            if template.name in self.skip_stages:
                continue

            # Apply custom prompt if provided
            if template.name in self.custom_prompts:
                modified_template = StageTemplate(
                    name=template.name,
                    prompt_template=self.custom_prompts[template.name],
                    requires_approval=template.requires_approval,
                    critical_path=template.critical_path,
                    skip_tests=template.skip_tests,
                    max_tokens=template.max_tokens,
                    temperature=template.temperature,
                )
                result.append(modified_template.to_stage(
                    project_path=project_path, **kwargs
                ))
            else:
                result.append(template.to_stage(
                    project_path=project_path, **kwargs
                ))

        return result


def get_default_stages(workflow_type: str = "llm-wrapper") -> list[StageTemplate]:
    """
    Get default stages for a workflow type.

    Args:
        workflow_type: Type of workflow (llm-wrapper, api, frontend)

    Returns:
        List of StageTemplate instances
    """
    stage_map = {
        "llm-wrapper": LLM_WRAPPER_STAGES,
        "api": API_DEVELOPMENT_STAGES,
        "frontend": FRONTEND_STAGES,
    }

    return stage_map.get(workflow_type, LLM_WRAPPER_STAGES)


def create_stage_config(
    workflow_type: str = "llm-wrapper",
    skip_stages: Optional[list[str]] = None,
    custom_prompts: Optional[dict[str, str]] = None,
) -> StageConfig:
    """
    Create a stage configuration for a workflow.

    Args:
        workflow_type: Type of workflow
        skip_stages: Stages to skip
        custom_prompts: Custom prompts to override defaults

    Returns:
        Configured StageConfig instance
    """
    return StageConfig(
        stages=get_default_stages(workflow_type),
        skip_stages=skip_stages or [],
        custom_prompts=custom_prompts or {},
    )
