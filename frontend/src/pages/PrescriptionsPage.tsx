import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  createMedicine,
  getPrescription,
  listPrescriptions,
  PrescriptionRejectedError,
  updatePrescriptionCandidate,
  uploadPrescription,
} from "../api";
import type { Prescription } from "../api";
import ImageLightbox from "../components/ImageLightbox";
import Modal from "../components/Modal";

export default function PrescriptionsPage() {
  const { id } = useParams<{ id: string }>();
  const patientId = id!;
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [activePrescription, setActivePrescription] = useState<Prescription | null>(null);
  const [uploading, setUploading] = useState(false);
  const [showUploadOptions, setShowUploadOptions] = useState(false);
  const [viewingPrescription, setViewingPrescription] = useState<Prescription | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [rejectionMessage, setRejectionMessage] = useState<string | null>(null);

  function refreshList() {
    listPrescriptions(patientId).then(setPrescriptions);
  }

  useEffect(() => {
    refreshList();
  }, [patientId]);

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files ? Array.from(e.target.files) : [];
    setShowUploadOptions(false);
    if (files.length === 0) return;
    setUploading(true);
    setRejectionMessage(null);
    try {
      const prescription = await uploadPrescription(patientId, files);
      setActivePrescription(prescription);
      refreshList();
    } catch (err) {
      if (err instanceof PrescriptionRejectedError) {
        setRejectionMessage(err.message);
      } else {
        throw err;
      }
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleConfirm(index: number, name: string, dose: string) {
    if (!activePrescription) return;
    await createMedicine(patientId, name, dose);
    const updated = await updatePrescriptionCandidate(patientId, activePrescription.id, index, {
      status: "confirmed",
      name,
      dose,
    });
    setActivePrescription(updated);
    refreshList();
  }

  async function handleSkip(index: number) {
    if (!activePrescription) return;
    const updated = await updatePrescriptionCandidate(patientId, activePrescription.id, index, {
      status: "skipped",
    });
    setActivePrescription(updated);
    refreshList();
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-6 py-4">
          <Link to={`/patients/${patientId}`} className="text-sm text-slate-500 hover:text-slate-700">
            ← Back
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-10">
        <div className="relative mb-6 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-slate-900">Prescriptions</h1>
          <div className="relative">
            <button
              onClick={() => setShowUploadOptions((v) => !v)}
              disabled={uploading}
              className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {uploading ? "Uploading…" : "Add prescription"}
            </button>

            {showUploadOptions && !uploading && (
              <div className="absolute right-0 z-10 mt-2 w-56 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
                <label className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100">
                  📁 Upload from files
                  <input
                    type="file"
                    accept="image/*,application/pdf"
                    multiple
                    className="hidden"
                    onChange={handleFileSelected}
                  />
                </label>
                <label className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100">
                  📷 Take a photo
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    multiple
                    className="hidden"
                    onChange={handleFileSelected}
                  />
                </label>
              </div>
            )}
          </div>
        </div>

        {rejectionMessage && (
          <div className="mb-6 flex items-start justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-5">
            <div>
              <p className="font-semibold text-amber-800">Oops, that doesn't look like a prescription</p>
              <p className="mt-1 text-sm text-amber-700">{rejectionMessage}</p>
            </div>
            <button
              onClick={() => setRejectionMessage(null)}
              aria-label="Dismiss"
              className="rounded-lg px-2 py-1 text-amber-700 transition hover:bg-amber-100"
            >
              ✕
            </button>
          </div>
        )}

        {activePrescription && (
          <div className="mb-8 rounded-2xl border border-teal-200 bg-teal-50 p-6">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-teal-700">
              Review extracted medicines
            </h2>
            <div className="space-y-4">
              {activePrescription.candidates.map((candidate, index) => (
                <CandidateCard
                  key={index}
                  candidate={candidate}
                  onConfirm={(name, dose) => handleConfirm(index, name, dose)}
                  onSkip={() => handleSkip(index)}
                />
              ))}
            </div>
          </div>
        )}

        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Past uploads
        </h2>
        {prescriptions.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
            No prescriptions uploaded yet.
          </div>
        ) : (
          <ul className="space-y-2">
            {prescriptions.map((p) => (
              <li
                key={p.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
              >
                <button onClick={() => setViewingPrescription(p)} className="flex-1 text-left">
                  <p className="font-medium text-teal-700 hover:underline">
                    {new Date(p.uploaded_at).toLocaleDateString()}
                  </p>
                  <p className="text-sm text-slate-500">
                    {p.status === "reviewed" ? "Reviewed" : "Needs review"} · {p.images.length} image
                    {p.images.length === 1 ? "" : "s"}
                  </p>
                </button>
                {p.status === "pending_review" && (
                  <button
                    onClick={() => getPrescription(patientId, p.id).then(setActivePrescription)}
                    className="text-sm font-medium text-teal-700 hover:text-teal-900"
                  >
                    Review →
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </main>

      {viewingPrescription && (
        <Modal
          title={`Prescription from ${new Date(viewingPrescription.uploaded_at).toLocaleDateString()}`}
          onClose={() => setViewingPrescription(null)}
        >
          <section className="mb-6">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
              Medicines from this prescription
            </h3>
            {viewingPrescription.candidates.filter((c) => c.status === "confirmed").length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
                No medicines were confirmed from this upload.
              </div>
            ) : (
              <ul className="space-y-2">
                {viewingPrescription.candidates
                  .filter((c) => c.status === "confirmed")
                  .map((c, index) => (
                    <li key={index} className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                      <p className="font-medium text-slate-900">
                        {c.name} — {c.dose}
                      </p>
                    </li>
                  ))}
              </ul>
            )}
          </section>

          <section>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
              Images ({viewingPrescription.images.length})
            </h3>
            <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
              {viewingPrescription.images.map((image, index) => (
                <button
                  key={image.id}
                  onClick={() => setLightboxIndex(index)}
                  className="aspect-square overflow-hidden rounded-xl border border-slate-200 bg-white"
                >
                  <img
                    src={image.file_url}
                    alt={`Prescription page ${index + 1}`}
                    className="h-full w-full object-cover"
                  />
                </button>
              ))}
            </div>
          </section>
        </Modal>
      )}

      {viewingPrescription && lightboxIndex !== null && (
        <ImageLightbox
          images={viewingPrescription.images}
          startIndex={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
        />
      )}
    </div>
  );
}

function CandidateCard({
  candidate,
  onConfirm,
  onSkip,
}: {
  candidate: { name: string; dose: string; frequency_hint: string; status: string };
  onConfirm: (name: string, dose: string) => void;
  onSkip: () => void;
}) {
  const [name, setName] = useState(candidate.name);
  const [dose, setDose] = useState(candidate.dose);

  if (candidate.status !== "pending") {
    return (
      <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
        <p className="font-medium text-slate-900">
          {candidate.name} — {candidate.dose}
        </p>
        <p className="text-sm text-slate-500">
          {candidate.status === "confirmed" ? "Confirmed ✓ — set up its schedule from the Medicines list" : "Skipped"}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Dose</label>
          <input
            value={dose}
            onChange={(e) => setDose(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900"
          />
        </div>
      </div>
      {candidate.frequency_hint && (
        <p className="mb-3 text-sm text-slate-500">AI read: {candidate.frequency_hint}</p>
      )}
      <div className="flex gap-2">
        <button
          onClick={() => onConfirm(name, dose)}
          className="flex-1 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
        >
          Confirm
        </button>
        <button
          onClick={onSkip}
          className="flex-1 rounded-lg bg-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-300"
        >
          Skip
        </button>
      </div>
    </div>
  );
}
