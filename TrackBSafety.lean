/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0

Independent finite invariant certificates for the frozen TrackB kernel.
-/

import TrackBSemantics

namespace TrackBReplay

abbrev SafetyCertificate (arity : Nat) := List (KernelState arity)

/--
Check that the supplied finite state set contains the initial state, contains
no forbidden state, and is closed under every enabled kernel transition.
-/
def SafetyCertificate.check
    (kernel : Kernel arity)
    (certificate : SafetyCertificate arity) : Bool :=
  certificate.contains kernel.initial &&
  certificate.all (fun state => !kernel.forbiddenHolds state) &&
  certificate.all fun before =>
    (kernel.successors before).all fun successor =>
      certificate.contains successor.2

def SafetyCertificate.Valid
    (kernel : Kernel arity)
    (certificate : SafetyCertificate arity) : Prop :=
  kernel.initial ∈ certificate ∧
  (∀ state, state ∈ certificate → ¬kernel.Forbidden state) ∧
  (∀ before, before ∈ certificate →
    ∀ actionName after,
      kernel.Transition before actionName after →
      after ∈ certificate)

theorem SafetyCertificate.check_iff
    {kernel : Kernel arity}
    {certificate : SafetyCertificate arity} :
    certificate.check kernel = true ↔ certificate.Valid kernel := by
  simp [
    SafetyCertificate.check,
    SafetyCertificate.Valid,
    Kernel.Forbidden,
    Kernel.Transition,
    and_assoc
  ]

/--
A passing finite certificate proves safety for every unboundedly reachable
state of the exact kernel transition system.
-/
theorem SafetyCertificate.check_sound
    {kernel : Kernel arity}
    {certificate : SafetyCertificate arity}
    (hcheck : certificate.check kernel = true) :
    ∀ state, kernel.Reachable state → ¬kernel.Forbidden state := by
  have hvalid := SafetyCertificate.check_iff.mp hcheck
  intro state hreachable
  have hmember : state ∈ certificate := by
    induction hreachable with
    | initial =>
        exact hvalid.1
    | step hreach htransition ih =>
        exact hvalid.2.2 _ ih _ _ htransition
  exact hvalid.2.1 state hmember

end TrackBReplay
