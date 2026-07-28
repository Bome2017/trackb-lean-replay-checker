/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0

Concrete, kernel-reducible safety certificates for the three guarded TrackB
workflows.  These proofs use kernel reduction and no fixture-specific
assumption.

The workflow values below are the exact typed values expected from the native
Lean JSON parser.  `trackb-guarded-fixture-check` checks that correspondence
against the checked-in JSON bytes, while the release gate binds those bytes to
their published SHA-256 values.
-/

import TrackBResults

namespace TrackBReplay.GuardedExamples

def invalidWorkflow : Workflow :=
  {
    schemaVersion := ""
    name := ""
    bound := 0
    variables := []
    initialState := []
    actions := []
    forbidden := []
  }

private def compileFixture
    (workflow : Workflow)
    (success : workflow.compile.isOk = true) :
    CompiledWorkflow workflow :=
  match hcompile : workflow.compile with
  | .ok kernel => { kernel, compiled := hcompile }
  | .error _ => by
      simp [hcompile, Except.isOk, Except.toBool] at success

theorem globallySafe_of_certificate
    {workflow : Workflow}
    {kernel : Kernel workflow.variables.length}
    {certificate : SafetyCertificate workflow.variables.length}
    (hcompile : workflow.compile = .ok kernel)
    (hcertificate : SafetyCertificate.check kernel certificate = true) :
    workflow.GloballySafe :=
  ⟨kernel, hcompile, SafetyCertificate.check_sound hcertificate⟩

theorem invalidWorkflow_not_globally_safe :
    ¬invalidWorkflow.GloballySafe := by
  rintro ⟨kernel, hcompile, _⟩
  simp [
    invalidWorkflow,
    Workflow.compile,
    Workflow.WellFormed
  ] at hcompile

def emailWorkflow : Workflow :=
  {
    schemaVersion := "0.1"
    name := "agent_email_requires_approval"
    bound := 5
    variables := [
      "approval_received",
      "approval_requested",
      "emailed_external",
      "file_deleted",
      "has_customer_data",
      "has_file",
      "summary_created"
    ]
    initialState := [
      ("approval_received", false),
      ("approval_requested", false),
      ("emailed_external", false),
      ("file_deleted", false),
      ("has_customer_data", false),
      ("has_file", true),
      ("summary_created", false)
    ]
    actions := [
      {
        name := "access_customer_data"
        pre := [("file_deleted", false), ("has_file", true)]
        effects := [("has_customer_data", true)]
      },
      {
        name := "summarize_file"
        pre := [("has_customer_data", true)]
        effects := [("summary_created", true)]
      },
      {
        name := "email_external"
        pre := [
          ("approval_received", true),
          ("summary_created", true)
        ]
        effects := [("emailed_external", true)]
      },
      {
        name := "request_approval"
        pre := [("summary_created", true)]
        effects := [("approval_requested", true)]
      },
      {
        name := "receive_approval"
        pre := [("approval_requested", true)]
        effects := [("approval_received", true)]
      }
    ]
    forbidden := [
      ("approval_received", false),
      ("emailed_external", true),
      ("has_customer_data", true)
    ]
  }

def emailCompiled : CompiledWorkflow emailWorkflow :=
  compileFixture emailWorkflow (by rfl)

def emailKernel : Kernel emailWorkflow.variables.length :=
  emailCompiled.kernel

def emailCertificate :
    SafetyCertificate emailWorkflow.variables.length :=
  [
    #v[false, false, false, false, false, true, false],
    #v[false, false, false, false, true, true, false],
    #v[false, false, false, false, true, true, true],
    #v[false, true, false, false, true, true, true],
    #v[true, true, false, false, true, true, true],
    #v[true, true, true, false, true, true, true]
  ]

theorem emailFixture_compile :
    emailWorkflow.compile = .ok emailKernel := by
  exact emailCompiled.compiled

theorem emailCertificate_check :
    SafetyCertificate.check emailKernel emailCertificate = true := by
  rfl

theorem email_requires_approval_globally_safe :
    emailWorkflow.GloballySafe :=
  globallySafe_of_certificate
    emailFixture_compile emailCertificate_check

def deleteWorkflow : Workflow :=
  {
    schemaVersion := "0.1"
    name := "agent_delete_requires_confirmation"
    bound := 4
    variables := [
      "confirmation_received",
      "confirmation_requested",
      "file_deleted",
      "file_exists",
      "file_selected"
    ]
    initialState := [
      ("confirmation_received", false),
      ("confirmation_requested", false),
      ("file_deleted", false),
      ("file_exists", true),
      ("file_selected", false)
    ]
    actions := [
      {
        name := "select_file"
        pre := [("file_deleted", false), ("file_exists", true)]
        effects := [("file_selected", true)]
      },
      {
        name := "delete_file"
        pre := [
          ("confirmation_received", true),
          ("file_selected", true)
        ]
        effects := [
          ("file_deleted", true),
          ("file_exists", false)
        ]
      },
      {
        name := "request_confirmation"
        pre := [("file_selected", true)]
        effects := [("confirmation_requested", true)]
      },
      {
        name := "receive_confirmation"
        pre := [("confirmation_requested", true)]
        effects := [("confirmation_received", true)]
      }
    ]
    forbidden := [
      ("confirmation_received", false),
      ("file_deleted", true)
    ]
  }

def deleteCompiled : CompiledWorkflow deleteWorkflow :=
  compileFixture deleteWorkflow (by rfl)

def deleteKernel : Kernel deleteWorkflow.variables.length :=
  deleteCompiled.kernel

def deleteCertificate :
    SafetyCertificate deleteWorkflow.variables.length :=
  [
    #v[false, false, false, true, false],
    #v[false, false, false, true, true],
    #v[false, true, false, true, true],
    #v[true, true, false, true, true],
    #v[true, true, true, false, true]
  ]

theorem deleteFixture_compile :
    deleteWorkflow.compile = .ok deleteKernel := by
  exact deleteCompiled.compiled

theorem deleteCertificate_check :
    SafetyCertificate.check deleteKernel deleteCertificate = true := by
  rfl

theorem delete_requires_confirmation_globally_safe :
    deleteWorkflow.GloballySafe :=
  globallySafe_of_certificate
    deleteFixture_compile deleteCertificate_check

def vendorPaymentWorkflow : Workflow :=
  {
    schemaVersion := "0.1"
    name := "agent_vendor_payment_guarded"
    bound := 8
    variables := [
      "compliance_review_passed",
      "invoice_read",
      "invoice_received",
      "manager_approved",
      "payment_system_accessed",
      "vendor_record_accessed",
      "vendor_verified",
      "wire_prepared",
      "wire_sent"
    ]
    initialState := [
      ("compliance_review_passed", false),
      ("invoice_read", false),
      ("invoice_received", true),
      ("manager_approved", false),
      ("payment_system_accessed", false),
      ("vendor_record_accessed", false),
      ("vendor_verified", false),
      ("wire_prepared", false),
      ("wire_sent", false)
    ]
    actions := [
      {
        name := "read_invoice"
        pre := [("invoice_received", true)]
        effects := [("invoice_read", true)]
      },
      {
        name := "access_vendor_record"
        pre := [("invoice_read", true)]
        effects := [("vendor_record_accessed", true)]
      },
      {
        name := "access_payment_system"
        pre := [("invoice_read", true)]
        effects := [("payment_system_accessed", true)]
      },
      {
        name := "verify_vendor"
        pre := [("vendor_record_accessed", true)]
        effects := [("vendor_verified", true)]
      },
      {
        name := "prepare_wire"
        pre := [
          ("payment_system_accessed", true),
          ("vendor_record_accessed", true)
        ]
        effects := [("wire_prepared", true)]
      },
      {
        name := "compliance_review"
        pre := [("wire_prepared", true)]
        effects := [("compliance_review_passed", true)]
      },
      {
        name := "manager_approve"
        pre := [("wire_prepared", true)]
        effects := [("manager_approved", true)]
      },
      {
        name := "send_wire"
        pre := [
          ("compliance_review_passed", true),
          ("manager_approved", true),
          ("vendor_verified", true),
          ("wire_prepared", true)
        ]
        effects := [("wire_sent", true)]
      }
    ]
    forbidden := [
      ("vendor_verified", false),
      ("wire_sent", true)
    ]
  }

def vendorPaymentCompiled : CompiledWorkflow vendorPaymentWorkflow :=
  compileFixture vendorPaymentWorkflow (by rfl)

def vendorPaymentKernel :
    Kernel vendorPaymentWorkflow.variables.length :=
  vendorPaymentCompiled.kernel

def vendorPaymentCertificate :
    SafetyCertificate vendorPaymentWorkflow.variables.length :=
  [
    #v[false, false, true, false, false, false, false, false, false],
    #v[false, true, true, false, false, false, false, false, false],
    #v[false, true, true, false, false, true, false, false, false],
    #v[false, true, true, false, true, false, false, false, false],
    #v[false, true, true, false, true, true, false, false, false],
    #v[false, true, true, false, false, true, true, false, false],
    #v[false, true, true, false, true, true, true, false, false],
    #v[false, true, true, false, true, true, false, true, false],
    #v[false, true, true, false, true, true, true, true, false],
    #v[true, true, true, false, true, true, false, true, false],
    #v[false, true, true, true, true, true, false, true, false],
    #v[true, true, true, false, true, true, true, true, false],
    #v[false, true, true, true, true, true, true, true, false],
    #v[true, true, true, true, true, true, false, true, false],
    #v[true, true, true, true, true, true, true, true, false],
    #v[true, true, true, true, true, true, true, true, true]
  ]

theorem vendorPaymentFixture_compile :
    vendorPaymentWorkflow.compile = .ok vendorPaymentKernel := by
  exact vendorPaymentCompiled.compiled

theorem vendorPaymentCertificate_check :
    SafetyCertificate.check
      vendorPaymentKernel vendorPaymentCertificate = true := by
  rfl

theorem vendor_payment_guarded_globally_safe :
    vendorPaymentWorkflow.GloballySafe :=
  globallySafe_of_certificate
    vendorPaymentFixture_compile vendorPaymentCertificate_check

def expectedWorkflow? (name : String) : Option Workflow :=
  if name == emailWorkflow.name then
    some emailWorkflow
  else if name == deleteWorkflow.name then
    some deleteWorkflow
  else if name == vendorPaymentWorkflow.name then
    some vendorPaymentWorkflow
  else
    none

end TrackBReplay.GuardedExamples
