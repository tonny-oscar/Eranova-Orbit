import { useState } from 'react'
import { Button } from '@/components/ui/button'

/** Two-step button for consequential actions: first click asks, second confirms. */
export function ConfirmButton({
  children,
  confirmLabel = 'Confirm',
  onConfirm,
  loading,
  variant = 'outline',
  confirmVariant = 'destructive',
  size = 'sm',
  disabled,
}) {
  const [asking, setAsking] = useState(false)
  if (!asking) {
    return (
      <Button variant={variant} size={size} disabled={disabled} onClick={() => setAsking(true)}>
        {children}
      </Button>
    )
  }
  return (
    <span className="inline-flex items-center gap-2" role="group" aria-label="Confirm action">
      <Button
        variant={confirmVariant}
        size={size}
        loading={loading}
        onClick={() => {
          onConfirm()
          setAsking(false)
        }}
      >
        {confirmLabel}
      </Button>
      <Button variant="ghost" size={size} onClick={() => setAsking(false)}>
        Cancel
      </Button>
    </span>
  )
}
