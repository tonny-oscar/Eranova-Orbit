import { Boxes, Search, UserRound } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { useGlobalSearch } from '@/features/dashboard/api'
import { useDebounced } from '@/hooks/useDebounced'
import { cn } from '@/lib/utils'

const ICONS = { product: Boxes, person: UserRound }
const TYPE_LABELS = { product: 'Product', person: 'Person' }

/** Header search (Ctrl/⌘+K) over records the user can access, as an ARIA combobox. */
export function GlobalSearch() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const listId = useId()
  const [value, setValue] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const q = useDebounced(value.trim(), 250)
  const { data, isFetching, isError } = useGlobalSearch(q)
  const results = q.length >= 2 ? (data?.results ?? []) : []

  useEffect(() => {
    const onKey = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const choose = (result) => {
    setOpen(false)
    setValue('')
    navigate(result.url)
  }

  const onKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setActive((i) => Math.min(i + 1, results.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (event.key === 'Enter' && results[active]) {
      event.preventDefault()
      choose(results[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
      inputRef.current?.blur()
    }
  }

  const showPanel = open && q.length >= 2

  return (
    <div className="relative w-full max-w-sm">
      <Search
        className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden="true"
      />
      <input
        ref={inputRef}
        type="search"
        role="combobox"
        aria-label="Search Orbit"
        aria-expanded={showPanel}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showPanel && results[active] ? `${listId}-${active}` : undefined}
        placeholder="Search products and people…"
        className="h-9 w-full rounded-md border border-input bg-navy-900/60 pl-9 pr-12 text-sm placeholder:text-muted-foreground"
        value={value}
        onChange={(e) => {
          setValue(e.target.value)
          setActive(0)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={onKeyDown}
      />
      <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border px-1.5 text-[10px] text-muted-foreground sm:block">
        Ctrl K
      </kbd>
      {showPanel && (
        <div className="absolute left-0 right-0 top-full z-40 mt-1 overflow-hidden rounded-lg border bg-card shadow-lg">
          <ul
            id={listId}
            role="listbox"
            aria-label="Search results"
            className="max-h-80 overflow-y-auto py-1"
          >
            {results.map((r, index) => {
              const Icon = ICONS[r.type] ?? Search
              return (
                <li
                  key={`${r.type}-${r.id}`}
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={index === active}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 px-3 py-2 text-sm',
                    index === active && 'bg-muted',
                  )}
                  onMouseEnter={() => setActive(index)}
                  onMouseDown={(e) => {
                    e.preventDefault()
                    choose(r)
                  }}
                >
                  <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{r.title}</span>
                    {r.subtitle && (
                      <span className="block truncate text-xs text-muted-foreground">
                        {r.subtitle}
                      </span>
                    )}
                  </span>
                  <span className="text-[10px] uppercase text-muted-foreground">
                    {TYPE_LABELS[r.type]}
                  </span>
                </li>
              )
            })}
          </ul>
          {results.length === 0 && (
            <p className="px-3 py-3 text-sm text-muted-foreground" role="status">
              {isError
                ? 'Search is unavailable right now.'
                : isFetching
                  ? 'Searching…'
                  : 'No matches you can access.'}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
