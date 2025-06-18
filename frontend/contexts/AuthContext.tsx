'use client'

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import Cookies from 'js-cookie'
import { api, authenticatedApi, endpoints, User, LoginRequest, TokenResponse, handleApiError } from '@/lib/api'

interface AuthContextType {
    user: User | null
    token: string | null
    isLoading: boolean
    login: (credentials: LoginRequest) => Promise<void>
    logout: () => void
    refreshToken: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const TOKEN_COOKIE_NAME = 'photo_timeline_token'
const REFRESH_TOKEN_COOKIE_NAME = 'photo_timeline_refresh_token'

interface AuthProviderProps {
    children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
    const [user, setUser] = useState<User | null>(null)
    const [token, setToken] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const router = useRouter()

    // Initialize auth state from cookies
    useEffect(() => {
        const initAuth = async () => {
            const storedToken = Cookies.get(TOKEN_COOKIE_NAME)

            if (storedToken) {
                setToken(storedToken)
                try {
                    // Verify token and get user info
                    const response = await authenticatedApi(storedToken).get(endpoints.me)
                    setUser(response.data)
                } catch (error) {
                    // Token is invalid, clear it
                    console.error('Token validation failed:', error)
                    clearAuth()
                }
            }

            setIsLoading(false)
        }

        initAuth()
    }, [])

    const login = async (credentials: LoginRequest) => {
        try {
            setIsLoading(true)

            // Send JSON login request
            const response = await api.post<TokenResponse>(endpoints.login, credentials)

            const { access_token, refresh_token } = response.data

            // Store tokens in cookies
            Cookies.set(TOKEN_COOKIE_NAME, access_token, {
                expires: 7, // 7 days
                secure: process.env.NODE_ENV === 'production',
                sameSite: 'lax',
            })

            if (refresh_token) {
                Cookies.set(REFRESH_TOKEN_COOKIE_NAME, refresh_token, {
                    expires: 30, // 30 days
                    secure: process.env.NODE_ENV === 'production',
                    sameSite: 'lax',
                })
            }

            setToken(access_token)

            // Get user info
            const userResponse = await authenticatedApi(access_token).get(endpoints.me)
            setUser(userResponse.data)

            // Redirect to groups page
            router.push('/groups')
        } catch (error) {
            const apiError = handleApiError(error)
            throw new Error(apiError.detail)
        } finally {
            setIsLoading(false)
        }
    }

    const logout = () => {
        clearAuth()
        router.push('/login')
    }

    const clearAuth = () => {
        Cookies.remove(TOKEN_COOKIE_NAME)
        Cookies.remove(REFRESH_TOKEN_COOKIE_NAME)
        setToken(null)
        setUser(null)
    }

    const refreshToken = async () => {
        const refreshTokenValue = Cookies.get(REFRESH_TOKEN_COOKIE_NAME)

        if (!refreshTokenValue) {
            logout()
            return
        }

        try {
            const response = await api.post<TokenResponse>('/auth/refresh', {
                refresh_token: refreshTokenValue,
            })

            const { access_token, refresh_token: newRefreshToken } = response.data

            // Update tokens
            Cookies.set(TOKEN_COOKIE_NAME, access_token, {
                expires: 7,
                secure: process.env.NODE_ENV === 'production',
                sameSite: 'lax',
            })

            if (newRefreshToken) {
                Cookies.set(REFRESH_TOKEN_COOKIE_NAME, newRefreshToken, {
                    expires: 30,
                    secure: process.env.NODE_ENV === 'production',
                    sameSite: 'lax',
                })
            }

            setToken(access_token)
        } catch (error) {
            console.error('Token refresh failed:', error)
            logout()
        }
    }

    const value: AuthContextType = {
        user,
        token,
        isLoading,
        login,
        logout,
        refreshToken,
    }

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
} 