'use client';

import {
    createContext,
    useContext,
    useEffect,
    useReducer,
    type ReactNode,
} from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export interface AuthUser {
    id: number;
    full_name_ar: string;
    username: string;
    role: string;
    departments: string[];
    specialization: string | null;
}

interface AuthContextType {
    user: AuthUser | null;
    token: string | null;
    isLoading: boolean;
    login: (user: AuthUser, token?: string | null) => void;
    logout: () => void;
}

type AuthState = {
    user: AuthUser | null;
    token: string | null;
    isLoading: boolean;
};

type AuthAction =
    | { type: 'hydrate'; payload: { user: AuthUser | null; token: string | null } }
    | { type: 'login'; payload: { user: AuthUser; token: string | null } }
    | { type: 'logout' };

const AuthContext = createContext<AuthContextType>({
    user: null,
    token: null,
    isLoading: false,
    login: (_user?: AuthUser, _token?: string | null) => undefined,
    logout: () => undefined,
});

const PUBLIC_PATHS = ['/login'];
const AUTH_TOKEN_KEY = 'echorouk_access_token';

function getHomePathByRole(role: string): string {
    const normalized = (role || '').toLowerCase();
    if (normalized === 'director' || normalized === 'editor_chief') return '/';
    return '/news';
}

export const useAuth = () => useContext(AuthContext);

function authReducer(state: AuthState, action: AuthAction): AuthState {
    switch (action.type) {
        case 'hydrate':
            return {
                token: action.payload.token,
                user: action.payload.user,
                isLoading: false,
            };
        case 'login':
            return {
                token: action.payload.token,
                user: action.payload.user,
                isLoading: false,
            };
        case 'logout':
            return {
                token: null,
                user: null,
                isLoading: false,
            };
        default:
            return state;
    }
}

function applyAuthToken(token: string | null) {
    if (token) {
        api.defaults.headers.common.Authorization = `Bearer ${token}`;
    } else {
        delete api.defaults.headers.common.Authorization;
    }
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();

    const [authState, dispatch] = useReducer(authReducer, {
        user: null,
        token: null,
        isLoading: true,
    });
    const { user, token, isLoading } = authState;

    useEffect(() => {
        let cancelled = false;

        const hydrate = async () => {
            try {
                const storedToken = typeof window !== 'undefined' ? localStorage.getItem(AUTH_TOKEN_KEY) : null;
                if (storedToken) {
                    applyAuthToken(storedToken);
                }
                const response = await api.get<AuthUser>('/auth/me');
                if (cancelled) return;
                dispatch({ type: 'hydrate', payload: { user: response.data, token: storedToken } });
            } catch {
                if (cancelled) return;
                if (typeof window !== 'undefined') {
                    localStorage.removeItem(AUTH_TOKEN_KEY);
                }
                applyAuthToken(null);
                dispatch({ type: 'hydrate', payload: { user: null, token: null } });
            }
        };

        void hydrate();

        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        if (isLoading) return;
        if (PUBLIC_PATHS.includes(pathname)) return;
        if (!user) router.push('/login');
    }, [isLoading, pathname, router, user]);

    const login = (newUser: AuthUser, _token: string | null = null) => {
        const resolvedToken = _token || null;
        if (typeof window !== 'undefined' && resolvedToken) {
            localStorage.setItem(AUTH_TOKEN_KEY, resolvedToken);
        }
        applyAuthToken(resolvedToken);
        dispatch({ type: 'login', payload: { user: newUser, token: resolvedToken } });
        router.push(getHomePathByRole(newUser.role));
    };

    const logout = async () => {
        try {
            await api.post('/auth/logout');
        } catch {
            // ignore network/logout errors
        }

        if (typeof window !== 'undefined') {
            localStorage.removeItem(AUTH_TOKEN_KEY);
        }
        applyAuthToken(null);
        dispatch({ type: 'logout' });
        router.push('/login');
    };

    return (
        <AuthContext.Provider value={{ user, token, isLoading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

