/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0
-/

import GuardedExamples

#print axioms TrackBReplay.KernelState.toBoolMap_keys
#print axioms TrackBReplay.KernelState.toKernelState_toBoolMap
#print axioms TrackBReplay.Kernel.transitionB_iff
#print axioms TrackBReplay.SafetyCertificate.check_iff
#print axioms TrackBReplay.SafetyCertificate.check_sound
#print axioms TrackBReplay.SemanticTrace.validB_iff
#print axioms TrackBReplay.SemanticTrace.states_ne_nil
#print axioms TrackBReplay.SemanticTrace.priorSafeB_iff
#print axioms TrackBReplay.boundedCounterexampleB_iff
#print axioms TrackBReplay.Kernel.mem_stateLayer_iff
#print axioms TrackBReplay.SemanticTrace.Valid.reachableAt
#print axioms TrackBReplay.Kernel.stateLayer_mem_stateLayers_of_le
#print axioms TrackBReplay.Kernel.mem_coveredStates_of_reachableAt
#print axioms TrackBReplay.findBadState?_none_no_boundedCounterexample
#print axioms TrackBReplay.SemanticTrace.valid_mem_traceLayer
#print axioms TrackBReplay.SemanticTrace.valid_mem_tracesUpTo
#print axioms TrackBReplay.findBoundedCounterexample?_sound
#print axioms TrackBReplay.findBoundedCounterexample?_complete
#print axioms TrackBReplay.findBoundedCounterexample?_none_iff
#print axioms TrackBReplay.reachabilityEngine_unsafe_sound
#print axioms TrackBReplay.reachabilityEngine_bounded_complete
#print axioms TrackBReplay.reachabilityEngine_not_unsafe_complete
#print axioms TrackBReplay.reachabilityEngine_safeWithinBound_sound
#print axioms TrackBReplay.reachabilityEngine_globallySafe_no_boundedCounterexample
#print axioms TrackBReplay.reachabilityEngine_globallySafe_sound
#print axioms TrackBReplay.check_iff
#print axioms TrackBReplay.check_sound
#print axioms TrackBReplay.check_complete
#print axioms TrackBReplay.GlobalSafetyResult.check_sound
#print axioms TrackBReplay.generated_global_result_is_globally_safe
#print axioms TrackBReplay.checked_unsafe_endToEnd
#print axioms TrackBReplay.checked_bounded_safe_endToEnd
#print axioms TrackBReplay.checked_global_endToEnd
#print axioms TrackBReplay.GuardedExamples.globallySafe_of_certificate
#print axioms TrackBReplay.GuardedExamples.invalidWorkflow_not_globally_safe
#print axioms TrackBReplay.GuardedExamples.emailFixture_compile
#print axioms TrackBReplay.GuardedExamples.emailCertificate_check
#print axioms TrackBReplay.GuardedExamples.email_requires_approval_globally_safe
#print axioms TrackBReplay.GuardedExamples.deleteFixture_compile
#print axioms TrackBReplay.GuardedExamples.deleteCertificate_check
#print axioms TrackBReplay.GuardedExamples.delete_requires_confirmation_globally_safe
#print axioms TrackBReplay.GuardedExamples.vendorPaymentFixture_compile
#print axioms TrackBReplay.GuardedExamples.vendorPaymentCertificate_check
#print axioms TrackBReplay.GuardedExamples.vendor_payment_guarded_globally_safe

-- Compile-check the exact result-bearing bounded-safety theorem shape.  A
-- theorem that drops the native result parameter cannot satisfy this example.
example
    {workflow : TrackBReplay.Workflow}
    {compiled : TrackBReplay.CompiledWorkflow workflow}
    (generated :
      TrackBReplay.CheckedGeneratedBoundedSafety workflow compiled) :
    TrackBReplay.EndToEndBoundedSafety
      workflow compiled generated.result :=
  TrackBReplay.checked_bounded_safe_endToEnd generated
