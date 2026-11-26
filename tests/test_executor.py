from src.runtime.models import StepSpec, WorkflowSpec, StepStatus
from src.runtime.executor import WorkflowExecutor


def test_successful_multi_step_workflow():
    executor = WorkflowExecutor()

    # Register handlers
    def step1_handler(inputs):
        return {"entities": ["Order#992", "ACME Corp"]}, 0.95

    def step2_handler(inputs):
        return {"summary": f"Processed {len(inputs['entities'])} entities"}, 0.98

    executor.register_tool("extract_entities", step1_handler)
    executor.register_tool("generate_summary", step2_handler)

    workflow = WorkflowSpec(
        workflow_id="wf-test-success",
        name="Order Processing",
        steps=[
            StepSpec(
                step_id="s1",
                action_name="extract_entities",
                prompt_template="Extract entities from order text",
                confidence_threshold=0.85,
            ),
            StepSpec(
                step_id="s2",
                action_name="generate_summary",
                prompt_template="Summarize extracted entities",
                required_inputs=["entities"],
                confidence_threshold=0.90,
            ),
        ],
    )

    result = executor.execute(workflow, {"raw_text": "Sample order from ACME Corp"})
    assert result.status == StepStatus.COMPLETED
    assert result.outputs["entities"] == ["Order#992", "ACME Corp"]
    assert "summary" in result.outputs
    assert len(result.audit_log) == 2


def test_sensitive_operation_escalation():
    executor = WorkflowExecutor()

    workflow = WorkflowSpec(
        workflow_id="wf-test-sensitive",
        name="Sensitive ERP Write",
        steps=[
            StepSpec(
                step_id="s1",
                action_name="post_ledger_transaction",
                prompt_template="Post debit transaction to general ledger",
                is_sensitive=True,
            )
        ],
    )

    result = executor.execute(workflow, {"amount": 50000})
    assert result.status == StepStatus.ESCALATED
    assert result.escalation is not None
    assert "sensitive" in result.escalation.reason.lower()
    assert result.escalation.step_id == "s1"


def test_low_confidence_escalation():
    executor = WorkflowExecutor()

    def uncertain_handler(inputs):
        return {"classification": "Disputed"}, 0.65  # below 0.85 threshold

    executor.register_tool("classify_intent", uncertain_handler)

    workflow = WorkflowSpec(
        workflow_id="wf-test-confidence",
        name="Intent Classification",
        steps=[
            StepSpec(
                step_id="s1",
                action_name="classify_intent",
                prompt_template="Classify customer message intent",
                confidence_threshold=0.85,
            )
        ],
    )

    result = executor.execute(workflow, {"message": "Ambiguous complaint"})
    assert result.status == StepStatus.ESCALATED
    assert result.escalation is not None
    assert "0.65" in result.escalation.reason


def test_missing_input_failure():
    executor = WorkflowExecutor()

    workflow = WorkflowSpec(
        workflow_id="wf-test-missing-input",
        name="Strict Input Validation",
        steps=[
            StepSpec(
                step_id="s1",
                action_name="parse_invoice",
                prompt_template="Parse invoice",
                required_inputs=["invoice_pdf_url"],
            )
        ],
    )

    result = executor.execute(workflow, {"order_id": 123})
    assert result.status == StepStatus.FAILED
    assert "invoice_pdf_url" in result.audit_log[0]["error"]
