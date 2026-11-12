import { Search, Users } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { useDebounced } from '@/hooks/useDebounced'
import { EMPLOYMENT_TYPES, useDepartments, useEmployees } from './api'
import { TeamTabs } from './TeamTabs'

const PAGE_SIZE = 25
const typeLabel = (value) => EMPLOYMENT_TYPES.find((t) => t.value === value)?.label

function PeopleTable() {
  const departments = useDepartments()
  const [search, setSearch] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [offset, setOffset] = useState(0)
  const q = useDebounced(search.trim())
  const { data, isPending, isError, error, refetch, isFetching } = useEmployees({
    q,
    department_id: departmentId,
    limit: PAGE_SIZE,
    offset,
  })

  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="people-search">Search</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="people-search"
              type="search"
              placeholder="Name or email"
              className="w-72 pl-9"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setOffset(0)
              }}
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="people-department">Department</Label>
          <Select
            id="people-department"
            className="w-56"
            value={departmentId}
            onChange={(e) => {
              setDepartmentId(e.target.value)
              setOffset(0)
            }}
          >
            <option value="">All departments</option>
            {(departments.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {isPending && <LoadingState label="Loading people…" />}
      {isError && <ErrorState title="Couldn't load people" error={error} onRetry={refetch} />}
      {data && data.items.length === 0 && (
        <EmptyState icon={Users} title="No people match" description="Try a different filter." />
      )}
      {data && data.items.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-busy={isFetching}>
              <caption className="sr-only">People directory</caption>
              <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Name
                  </th>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Role
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                    Department
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                    Manager
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.items.map((e) => (
                  <tr key={e.user.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3">
                      <Link to={`/app/team/${e.user.id}`} className="font-medium hover:text-accent">
                        {e.user.full_name}
                      </Link>
                      <p className="text-xs text-muted-foreground">{e.user.email}</p>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {e.job_title ?? (e.has_profile ? '—' : 'Profile not set up')}
                      {e.employment_type && e.employment_type !== 'full_time' && (
                        <span className="block text-xs">{typeLabel(e.employment_type)}</span>
                      )}
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                      {e.department?.name ?? '—'}
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">
                      {e.manager?.full_name ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-muted-foreground">
            <span>
              {data.offset + 1}–{data.offset + data.items.length} of {data.total}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={data.offset + data.items.length >= data.total}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </Card>
      )}
    </>
  )
}

export function TeamPage() {
  return (
    <>
      <PageHeader title="Team" description="People, departments and reporting lines." />
      <TeamTabs />
      <RequirePermission permission="employee.read">
        <PeopleTable />
      </RequirePermission>
    </>
  )
}
