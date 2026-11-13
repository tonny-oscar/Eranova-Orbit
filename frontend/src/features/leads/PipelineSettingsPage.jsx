import { ArrowDown, ArrowUp, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { stageVariant, useStageMutations, useStages } from './api'

function StageList() {
  const { data, isPending, isError, error, refetch } = useStages()
  const { create, update, remove } = useStageMutations()
  const [name, setName] = useState('')
  const failure = create.error ?? update.error ?? remove.error

  if (isPending) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const swap = (index, delta) => {
    const a = data[index]
    const b = data[index + delta]
    update.mutate({ id: a.id, position: b.position })
    update.mutate({ id: b.id, position: a.position })
  }

  return (
    <Card className="max-w-2xl">
      <CardContent className="space-y-4 pt-5">
        {failure && <Alert variant="error" title={failure.message} />}
        <ol className="divide-y">
          {data.map((stage, index) => (
            <li key={stage.id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <span className="flex items-center gap-2">
                <Badge variant={stageVariant(stage)}>{stage.name}</Badge>
                {stage.is_won && (
                  <span className="text-xs text-muted-foreground">counts as won</span>
                )}
                {stage.is_lost && (
                  <span className="text-xs text-muted-foreground">counts as lost</span>
                )}
              </span>
              <span className="flex gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Move ${stage.name} up`}
                  disabled={index === 0}
                  onClick={() => swap(index, -1)}
                >
                  <ArrowUp />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Move ${stage.name} down`}
                  disabled={index === data.length - 1}
                  onClick={() => swap(index, 1)}
                >
                  <ArrowDown />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Delete ${stage.name}`}
                  onClick={() => remove.mutate(stage.id)}
                >
                  <Trash2 />
                </Button>
              </span>
            </li>
          ))}
        </ol>
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate({ name: name.trim() }, { onSuccess: () => setName('') })
          }}
        >
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="stage-name">New stage</Label>
            <Input id="stage-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <Button
            type="submit"
            variant="outline"
            disabled={name.trim().length < 2}
            loading={create.isPending}
          >
            Add stage
          </Button>
        </form>
        <p className="text-xs text-muted-foreground">
          Stages in use cannot be deleted; move their leads first.
        </p>
      </CardContent>
    </Card>
  )
}

export function PipelineSettingsPage() {
  return (
    <>
      <PageHeader title="Sales pipeline" description="The stages leads move through." />
      <RequirePermission permission="lead.manage">
        <StageList />
      </RequirePermission>
    </>
  )
}
