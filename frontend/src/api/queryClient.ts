import { QueryClient } from '@tanstack/react-query'

import { ApiError } from './client'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // never retry what the server refused on purpose (401/403/404/422)
      retry: (failures, err) => !(err instanceof ApiError && err.status < 500) && failures < 2,
    },
  },
})
