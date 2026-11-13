import { Bell } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/hooks'
import { cn, formatDateTime } from '@/lib/utils'
import { useMarkNotificationsRead, useNotifications } from './api'

export function NotificationBell() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  const { data } = useNotifications()
  const markRead = useMarkNotificationsRead()
  const [open, setOpen] = useState(false)
  const panel = useRef(null)
  const unread = data?.unread ?? 0

  useEffect(() => {
    if (!open) return undefined
    const onClick = (e) => {
      if (panel.current && !panel.current.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="relative" ref={panel}>
      <Button
        variant="ghost"
        size="icon"
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Bell />
        {unread > 0 && (
          <span className="absolute right-1.5 top-1.5 grid min-w-4 place-items-center rounded-full bg-accent px-1 text-[10px] font-semibold text-accent-foreground">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </Button>
      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="absolute right-0 top-full z-40 mt-2 w-80 overflow-hidden rounded-lg border bg-card shadow-lg"
        >
          <div className="flex items-center justify-between border-b px-3 py-2 text-sm">
            <span className="font-medium">Notifications</span>
            {unread > 0 && (
              <button
                type="button"
                className="text-xs text-accent hover:underline"
                onClick={() => markRead.mutate(null)}
              >
                Mark all read
              </button>
            )}
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {(data?.items ?? []).length === 0 && (
              <li className="px-3 py-6 text-center text-sm text-muted-foreground">
                You're all caught up.
              </li>
            )}
            {(data?.items ?? []).map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  className={cn(
                    'block w-full px-3 py-2 text-left text-sm hover:bg-muted',
                    !n.read_at && 'bg-primary/5',
                  )}
                  onClick={() => {
                    if (!n.read_at) markRead.mutate(n.id)
                    setOpen(false)
                    if (n.link) navigate(n.link)
                  }}
                >
                  <p className={cn(!n.read_at && 'font-medium')}>{n.title}</p>
                  {n.body && <p className="truncate text-xs text-muted-foreground">{n.body}</p>}
                  <p className="text-[11px] text-muted-foreground">
                    {formatDateTime(n.created_at, me?.company?.timezone)}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
