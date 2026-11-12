import { Check, Copy, KeyRound } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

/** Shows an administrator-issued temporary password exactly once. */
export function TemporaryPasswordNotice({ email, password, onDismiss }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(password)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div role="status" className="space-y-3 rounded-lg border border-warning/40 bg-warning/10 p-4">
      <p className="flex items-center gap-2 font-medium">
        <KeyRound className="size-4 text-warning" aria-hidden="true" /> Temporary password for{' '}
        {email}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <code className="rounded-md bg-background px-3 py-2 font-mono text-sm tracking-wider">
          {password}
        </code>
        <Button variant="outline" size="sm" onClick={copy}>
          {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">
        This is shown only once. Share it with the person through a private channel; they must
        choose their own password when they first sign in.
      </p>
      {onDismiss && (
        <Button variant="ghost" size="sm" onClick={onDismiss}>
          Done
        </Button>
      )}
    </div>
  )
}
