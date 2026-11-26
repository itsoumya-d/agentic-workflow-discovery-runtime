from src.runtime.models import StepSpec, WorkflowSpec, StepStatus


def test_workflow_spec_initialization():
    step = StepSpec(
        step_id="step-1",
        action_name="extract_entities",
        prompt_template="Extract entities from {text}",
        is_sensitive=False,
    )
    workflow = WorkflowSpec(
        workflow_id="wf-101",
        name="CRM Entity Extraction",
        steps=[step],
    )
    assert workflow.workflow_id == "wf-101"
    assert len(workflow.steps) == 1
    assert workflow.steps[0].confidence_threshold == 0.85
