import { createContext, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  authApi,
  configApi,
  setTokenAccessor,
  setRefreshFn,
  setOnUnauthorized,
} from '../services/api'
import type { UserResponse } from '../services/api'
import i18n from '../i18n'

const REFRESH_TOKEN_KEY = 'spt_refresh_token'

interface AuthState {
  user: UserResponse | null
  accessToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshToken: () => Promise<string | null>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function applyTheme(theme: string) {
  const root = document.documentElement
  if (theme === 'dark') {
    root.classList.add('dark')
  } else if (theme === 'light') {
    root.classList.remove('dark')
  } else {
    // system
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    root.classList.toggle('dark', prefersDark)
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    isAuthenticated: false,
    isLoading: true,
  })

  // Keep a ref so interceptors always see the latest token without stale closure
  const accessTokenRef = useRef<string | null>(null)

  function setAccessToken(token: string | null) {
    accessTokenRef.current = token
    setState((s) => ({ ...s, accessToken: token }))
  }

  async function loadUserConfig(_token: string): Promise<UserResponse> {
    const me = await authApi.me()
    const user = me.data
    try {
      const cfg = await configApi.get()
      user.config = cfg.data
      i18n.changeLanguage(cfg.data.locale)
      applyTheme(cfg.data.theme)
    } catch {
      // config non-critical
    }
    return user
  }

  const refreshToken = async (): Promise<string | null> => {
    const stored = localStorage.getItem(REFRESH_TOKEN_KEY)
    if (!stored) return null
    try {
      const res = await authApi.refresh(stored)
      const newToken = res.data.access_token
      setAccessToken(newToken)
      return newToken
    } catch {
      localStorage.removeItem(REFRESH_TOKEN_KEY)
      setState({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
      return null
    }
  }

  // Wire up interceptor accessors once
  useEffect(() => {
    setTokenAccessor(() => accessTokenRef.current)
    setRefreshFn(refreshToken)
    setOnUnauthorized(() => {
      localStorage.removeItem(REFRESH_TOKEN_KEY)
      setState({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
    })
  }, [])

  // Silent restore on mount
  useEffect(() => {
    const stored = localStorage.getItem(REFRESH_TOKEN_KEY)
    if (!stored) {
      setState((s) => ({ ...s, isLoading: false }))
      return
    }
    ;(async () => {
      try {
        const res = await authApi.refresh(stored)
        const token = res.data.access_token
        accessTokenRef.current = token
        const user = await loadUserConfig(token)
        setState({ user, accessToken: token, isAuthenticated: true, isLoading: false })
      } catch {
        localStorage.removeItem(REFRESH_TOKEN_KEY)
        setState({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
      }
    })()
  }, [])

  const login = async (email: string, password: string) => {
    const res = await authApi.login(email, password)
    const { access_token, refresh_token } = res.data
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token)
    accessTokenRef.current = access_token
    const user = await loadUserConfig(access_token)
    setState({ user, accessToken: access_token, isAuthenticated: true, isLoading: false })
  }

  const logout = () => {
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    accessTokenRef.current = null
    setState({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
  }

  return (
    <AuthContext.Provider value={{ ...state, login, logout, refreshToken }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
