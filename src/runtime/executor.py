import time
import uuid
from typing import Dict, Any, Callable, Tuple
from .models import (
    StepStatus,
    StepSpec,
    WorkflowSpec,
    ExecutionResult,
    EscalationTicket,
)

ToolHandler = Callable[[Dict[str, Any]], Tuple[Dict[str, Any], float]]


class WorkflowExecutor:
    """Executes multi-step agent workflows with risk-aware human-in-the-loop escalation."""

    def __init__(self):
        self._tools: Dict[str, ToolHandler] = {}

    def register_tool(self, action_name: str, handler: ToolHandler) -> None:
        self._tools[action_name] = handler

    def execute(self, workflow: WorkflowSpec, initial_inputs: Dict[str, Any]) -> ExecutionResult:
        state: Dict[str, Any] = dict(initial_inputs)
        audit_log = []

        for step in workflow.steps:
            start_time = time.time()
            log_entry = {
                "step_id": step.step_id,
                "action_name": step.action_name,
                "start_time": start_time,
            }

            # 1. Validate required inputs
            missing_inputs = [inp for inp in step.required_inputs if inp not in state]
            if missing_inputs:
                log_entry["status"] = StepStatus.FAILED
                log_entry["error"] = f"Missing required inputs: {missing_inputs}"
                audit_log.append(log_entry)
                return ExecutionResult(
                    workflow_id=workflow.workflow_id,
                    status=StepStatus.FAILED,
                    outputs=state,
                    audit_log=audit_log,
                )

            # 2. Risk Gate: Sensitive operations require immediate human sign-off
            if step.is_sensitive:
                log_entry["status"] = StepStatus.ESCALATED
                log_entry["reason"] = "SENSITIVE_OPERATION_APPROVAL_REQUIRED"
                audit_log.append(log_entry)
                ticket = EscalationTicket(
                    ticket_id=f"TKT-{uuid.uuid4().hex[:8].upper()}",
                    workflow_id=workflow.workflow_id,
                    step_id=step.step_id,
                    reason="Step marked as sensitive; requires human confirmation before dispatch.",
                    context={"state": state, "step": step.model_dump()},
                )
                return ExecutionResult(
                    workflow_id=workflow.workflow_id,
                    status=StepStatus.ESCALATED,
                    outputs=state,
                    escalation=ticket,
                    audit_log=audit_log,
                )

            # 3. Lookup tool handler
            handler = self._tools.get(step.action_name)
            if not handler:
                log_entry["status"] = StepStatus.FAILED
                log_entry["error"] = f"Unregistered action handler: {step.action_name}"
                audit_log.append(log_entry)
                return ExecutionResult(
                    workflow_id=workflow.workflow_id,
                    status=StepStatus.FAILED,
                    outputs=state,
                    audit_log=audit_log,
                )

            # 4. Execute tool
            try:
                output, confidence = handler(state)
            except Exception as e:
                log_entry["status"] = StepStatus.FAILED
                log_entry["error"] = str(e)
                audit_log.append(log_entry)
                return ExecutionResult(
                    workflow_id=workflow.workflow_id,
                    status=StepStatus.FAILED,
                    outputs=state,
                    audit_log=audit_log,
                )

            log_entry["confidence"] = confidence
            log_entry["duration_ms"] = round((time.time() - start_time) * 1000, 2)

            # 5. Confidence Gate: Low confidence halts execution for human review
            if confidence < step.confidence_threshold:
                log_entry["status"] = StepStatus.ESCALATED
                log_entry["reason"] = "LOW_CONFIDENCE_ESCALATION"
                audit_log.append(log_entry)
                ticket = EscalationTicket(
                    ticket_id=f"TKT-{uuid.uuid4().hex[:8].upper()}",
                    workflow_id=workflow.workflow_id,
                    step_id=step.step_id,
                    reason=f"Action confidence {confidence:.2f} fell below required threshold {step.confidence_threshold:.2f}",
                    context={"output": output, "state": state},
                )
                return ExecutionResult(
                    workflow_id=workflow.workflow_id,
                    status=StepStatus.ESCALATED,
                    outputs=state,
                    escalation=ticket,
                    audit_log=audit_log,
                )

            # Step completed successfully; update state
            state.update(output)
            log_entry["status"] = StepStatus.COMPLETED
            audit_log.append(log_entry)

        return ExecutionResult(
            workflow_id=workflow.workflow_id,
            status=StepStatus.COMPLETED,
            outputs=state,
            audit_log=audit_log,
        )
