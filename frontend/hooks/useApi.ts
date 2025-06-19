import { useCallback } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { authenticatedApi, api, handleApiError } from '@/lib/api'
import type { ApiError } from '@/types'

interface UseApiOptions {
	requireAuth?: boolean
}

export const useApi = (options: UseApiOptions = {}) => {
	const { token } = useAuth()
	const { requireAuth = true } = options

	const makeRequest = useCallback(async <T>(
		method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH',
		url: string,
		data?: any,
		config?: any
	): Promise<T> => {
		try {
			const apiInstance = requireAuth && token ? authenticatedApi(token) : api
			
			let response
			switch (method) {
				case 'GET':
					response = await apiInstance.get(url, config)
					break
				case 'POST':
					response = await apiInstance.post(url, data, config)
					break
				case 'PUT':
					response = await apiInstance.put(url, data, config)
					break
				case 'DELETE':
					response = await apiInstance.delete(url, config)
					break
				case 'PATCH':
					response = await apiInstance.patch(url, data, config)
					break
				default:
					throw new Error(`Unsupported method: ${method}`)
			}
			
			return response.data
		} catch (error) {
			const apiError = handleApiError(error)
			throw apiError
		}
	}, [token, requireAuth])

	const get = useCallback(<T>(url: string, config?: any) => 
		makeRequest<T>('GET', url, undefined, config), [makeRequest])

	const post = useCallback(<T>(url: string, data?: any, config?: any) => 
		makeRequest<T>('POST', url, data, config), [makeRequest])

	const put = useCallback(<T>(url: string, data?: any, config?: any) => 
		makeRequest<T>('PUT', url, data, config), [makeRequest])

	const del = useCallback(<T>(url: string, config?: any) => 
		makeRequest<T>('DELETE', url, undefined, config), [makeRequest])

	const patch = useCallback(<T>(url: string, data?: any, config?: any) => 
		makeRequest<T>('PATCH', url, data, config), [makeRequest])

	return {
		get,
		post,
		put,
		delete: del,
		patch,
		makeRequest
	}
} 