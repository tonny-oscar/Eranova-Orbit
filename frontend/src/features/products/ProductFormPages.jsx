import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { useCreateProduct, useProduct, useUpdateProduct } from './api'
import { ProductForm } from './ProductForm'

function BackLink({ to, children }) {
  return (
    <Link
      to={to}
      className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" aria-hidden="true" /> {children}
    </Link>
  )
}

export function NewProductPage() {
  const navigate = useNavigate()
  const create = useCreateProduct()
  return (
    <>
      <BackLink to="/app/products">Products</BackLink>
      <PageHeader title="Register product" description="Add a product to the Eranova registry." />
      <RequirePermission permission="product.create">
        <ProductForm
          submitLabel="Register product"
          submitting={create.isPending}
          serverError={create.error}
          onSubmit={(payload) =>
            create.mutate(payload, {
              onSuccess: (product) => navigate(`/app/products/${product.id}`),
            })
          }
        />
      </RequirePermission>
    </>
  )
}

export function EditProductPage() {
  const { productId } = useParams()
  const navigate = useNavigate()
  const { data: product, isPending, isError, error, refetch } = useProduct(productId)
  const update = useUpdateProduct(productId)

  if (isPending) return <LoadingState label="Loading product…" />
  if (isError)
    return <ErrorState title="Couldn't load this product" error={error} onRetry={refetch} />

  return (
    <>
      <BackLink to={`/app/products/${productId}`}>{product.name}</BackLink>
      <PageHeader title={`Edit ${product.name}`} />
      {product.can_update ? (
        <ProductForm
          product={product}
          submitLabel="Save changes"
          submitting={update.isPending}
          serverError={update.error}
          onSubmit={(payload) =>
            update.mutate(payload, { onSuccess: () => navigate(`/app/products/${productId}`) })
          }
        />
      ) : (
        <ErrorState
          title="You can't edit this product"
          error={{ message: 'Ask a Super Admin for product edit access if you need it.' }}
        />
      )}
    </>
  )
}
