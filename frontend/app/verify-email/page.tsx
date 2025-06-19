'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { api, handleApiError } from '@/lib/api'

function VerifyEmailContent() {
	const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
	const [message, setMessage] = useState('')
	const [email, setEmail] = useState('')
	const searchParams = useSearchParams()
	const router = useRouter()
	const token = searchParams.get('token')

	useEffect(() => {
		if (!token) {
			setStatus('error')
			setMessage('No verification token provided')
			return
		}

		const verifyEmail = async () => {
			try {
				const response = await api.post('/auth/verify-email', null, {
					params: { token }
				})

				setStatus('success')
				setMessage(response.data.message)
				setEmail(response.data.email)

				// Redirect to login after 3 seconds
				setTimeout(() => {
					router.push('/login?message=Email verified! You can now sign in.')
				}, 3000)
			} catch (err) {
				const apiError = handleApiError(err)
				setStatus('error')
				setMessage(apiError.detail)
			}
		}

		verifyEmail()
	}, [token, router])

	if (status === 'loading') {
		return (
			<div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
				<div className="max-w-md w-full space-y-8">
					<div className="text-center">
						<div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
						<h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
							Verifying your email...
						</h2>
						<p className="mt-2 text-center text-sm text-gray-600">
							Please wait while we verify your email address.
						</p>
					</div>
				</div>
			</div>
		)
	}

	if (status === 'success') {
		return (
			<div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
				<div className="max-w-md w-full space-y-8">
					<div className="text-center">
						<div className="mx-auto h-12 w-12 bg-green-100 rounded-full flex items-center justify-center">
							<svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
							</svg>
						</div>
						<h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
							Email Verified Successfully!
						</h2>
						<p className="mt-2 text-center text-sm text-gray-600">
							Welcome to Photo Timeline! Your email {email} has been verified.
						</p>
						<p className="mt-2 text-center text-sm text-gray-500">
							Redirecting you to the login page...
						</p>
					</div>

					<div className="text-center">
						<Link
							href="/login"
							className="font-medium text-blue-600 hover:text-blue-500"
						>
							Go to Login →
						</Link>
					</div>
				</div>
			</div>
		)
	}

	return (
		<div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
			<div className="max-w-md w-full space-y-8">
				<div className="text-center">
					<div className="mx-auto h-12 w-12 bg-red-100 rounded-full flex items-center justify-center">
						<svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
						</svg>
					</div>
					<h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
						Verification Failed
					</h2>
					<p className="mt-2 text-center text-sm text-gray-600">
						{message}
					</p>
					<p className="mt-4 text-center text-sm text-gray-500">
						The verification link may have expired or been used already.
					</p>
				</div>

				<div className="text-center space-y-4">
					<Link
						href="/register"
						className="font-medium text-blue-600 hover:text-blue-500"
					>
						← Back to Registration
					</Link>
					<br />
					<Link
						href="/login"
						className="font-medium text-blue-600 hover:text-blue-500"
					>
						Try Signing In →
					</Link>
				</div>
			</div>
		</div>
	)
}

export default function VerifyEmailPage() {
	return (
		<Suspense fallback={
			<div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
				<div className="max-w-md w-full space-y-8">
					<div className="text-center">
						<div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
						<h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
							Loading...
						</h2>
					</div>
				</div>
			</div>
		}>
			<VerifyEmailContent />
		</Suspense>
	)
} 