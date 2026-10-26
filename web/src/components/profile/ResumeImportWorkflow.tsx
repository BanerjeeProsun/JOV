import React, { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Clock,
} from 'lucide-react'
import { Button } from '../ui/Button'
import { api } from '../../api/client'
import { spring, dur, ease } from '../../design/motion'

export type ImportStep =
  | 'empty'
  | 'fileSelected'
  | 'uploading'
  | 'processing'
  | 'awaitingReview'
  | 'completed'
  | 'failed'

interface ResumeImportWorkflowProps {
  candidateId: string
  hasExistingResume?: boolean
  onSuccess: () => void
}

const STEPS = [
  { id: 'select', label: '1. Document' },
  { id: 'upload', label: '2. Upload' },
  { id: 'process', label: '3. Extraction' },
  { id: 'review', label: '4. Verified' },
]

export const ResumeImportWorkflow: React.FC<ResumeImportWorkflowProps> = ({
  candidateId,
  hasExistingResume = false,
  onSuccess,
}) => {
  const [step, setStep] = useState<ImportStep>('empty')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [errorText, setErrorText] = useState<string | null>(null)
  const [extractedCount, setExtractedCount] = useState<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSelectFile = (file: File | undefined) => {
    if (!file) return
    setSelectedFile(file)
    setErrorText(null)
    setStep('fileSelected')
  }

  const handleUploadAndProcess = async () => {
    if (!selectedFile || !candidateId) return

    setStep('uploading')
    setErrorText(null)

    try {
      // Simulate real step transition to processing
      setTimeout(() => {
        setStep((curr) => (curr === 'uploading' ? 'processing' : curr))
      }, 350)

      const result = await api.uploadMasterResume(candidateId, selectedFile)
      setExtractedCount(result.total_facts_extracted)
      setStep('completed')
      onSuccess()
    } catch (err: any) {
      setErrorText(err.message || 'Resume parsing failed. Ensure file is a valid PDF or text.')
      setStep('failed')
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setErrorText(null)
    setStep('empty')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // Map step to indicator index
  const activeStepIndex =
    step === 'empty' || step === 'fileSelected'
      ? 0
      : step === 'uploading'
      ? 1
      : step === 'processing'
      ? 2
      : 3

  return (
    <div className="border-b border-border/60 pb-8 mb-8 space-y-6">
      {/* Segmented Step Indicator with layoutId highlight */}
      <div className="flex items-center justify-between gap-2 border-b border-border pb-4">
        {STEPS.map((s, idx) => {
          const isCurrent = idx === activeStepIndex
          const isDone = idx < activeStepIndex

          return (
            <div key={s.id} className="relative flex-1 text-center">
              <div
                className={`py-1 text-xs font-mono transition-colors ${
                  isCurrent ? 'text-text font-semibold' : isDone ? 'text-text-2' : 'text-text-3'
                }`}
              >
                {isDone ? `✓ ${s.label.split('. ')[1]}` : s.label}
              </div>
              {isCurrent && (
                <motion.div
                  layoutId="import-step-line"
                  className="absolute bottom-[-17px] left-0 right-0 h-[2px] bg-accent"
                  transition={spring.layout}
                />
              )}
            </div>
          )
        })}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.txt"
        onChange={(e) => handleSelectFile(e.target.files?.[0])}
        className="hidden"
      />

      {/* State Machine Panels */}
      <AnimatePresence mode="wait">
        {step === 'empty' && (
          <motion.div
            key="empty"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: dur.fast, ease: ease.out }}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              handleSelectFile(e.dataTransfer.files?.[0])
            }}
            onClick={() => fileInputRef.current?.click()}
            className="border border-border/70 hover:border-text-3 rounded-xl p-8 text-center cursor-pointer bg-bg-elev-1/20 hover:bg-bg-elev-1/50 transition-colors"
          >
            <Upload className="w-6 h-6 text-text-3 mx-auto mb-2.5" strokeWidth={1.5} />
            <h4 className="text-sm font-semibold text-text">
              {hasExistingResume ? 'Replace Master Resume' : 'Import Master Resume'}
            </h4>
            <p className="text-xs text-text-3 mt-1 max-w-sm mx-auto">
              Drag and drop your PDF CV here or click to browse.
            </p>
          </motion.div>
        )}

        {step === 'fileSelected' && selectedFile && (
          <motion.div
            key="fileSelected"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="p-6 border border-border/70 rounded-xl bg-bg-elev-1/30 space-y-4"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5 text-text-2" />
                <div>
                  <p className="text-sm font-semibold text-text">{selectedFile.name}</p>
                  <p className="text-xs text-text-3 font-mono">
                    {(selectedFile.size / 1024).toFixed(1)} KB · Ready to parse
                  </p>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={handleReset}>
                Cancel
              </Button>
            </div>

            <div className="flex justify-end pt-2">
              <Button variant="primary" size="md" onClick={handleUploadAndProcess}>
                <span>Upload & Extract Provenance</span>
              </Button>
            </div>
          </motion.div>
        )}

        {(step === 'uploading' || step === 'processing') && (
          <motion.div
            key="processing"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="p-10 border border-border/70 rounded-xl bg-bg-elev-1/30 text-center space-y-4"
          >
            <div className="w-10 h-10 rounded-full bg-bg-elev-1 border border-border flex items-center justify-center mx-auto text-text animate-pulse">
              <Clock className="w-5 h-5" />
            </div>

            <div>
              <h4 className="text-sm font-semibold text-text">
                {step === 'uploading' ? 'Uploading document…' : 'Extracting candidate facts…'}
              </h4>
              <p className="text-xs text-text-3 mt-1 font-mono">
                Running deterministic claim extraction with sentence-level provenance.
              </p>
            </div>

            {/* Indeterminate pearl shimmer line */}
            <div className="h-1 w-full max-w-xs mx-auto rounded-full bg-border overflow-hidden relative">
              <div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-text to-transparent"
                style={{ animation: 'pearl-shimmer 1.8s infinite ease-in-out' }}
              />
            </div>
          </motion.div>
        )}

        {step === 'completed' && (
          <motion.div
            key="completed"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="p-6 border border-border/70 rounded-xl bg-bg-elev-1/30 text-text space-y-3"
          >
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="w-5 h-5 text-text-2 shrink-0" />
              <h4 className="text-sm font-semibold">Extraction Complete</h4>
            </div>
            <p className="text-xs text-text-2 leading-relaxed">
              Extracted {extractedCount ?? 'all'} verified facts into the candidate graph. You can inspect claims in the sections below.
            </p>
            <div className="pt-2">
              <Button variant="secondary" size="sm" onClick={handleReset}>
                <span>Import Another File</span>
              </Button>
            </div>
          </motion.div>
        )}

        {step === 'failed' && (
          <motion.div
            key="failed"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="p-6 border border-border/70 rounded-xl bg-bg-elev-1/30 text-text space-y-3"
          >
            <div className="flex items-center gap-2.5">
              <AlertCircle className="w-5 h-5 text-text-3 shrink-0" />
              <h4 className="text-sm font-semibold">Processing Failed</h4>
            </div>
            <p className="text-xs text-text-2 leading-relaxed">{errorText}</p>
            <div className="pt-2">
              <Button variant="secondary" size="sm" onClick={handleReset}>
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Retry Import</span>
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
