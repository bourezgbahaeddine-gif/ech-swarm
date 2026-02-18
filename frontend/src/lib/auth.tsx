'use client';

import {
    createContext,
    useContext,
    useEffect,
    useMemo,
    useState,
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
    login: (token: string, user: AuthUser) => void;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    token: null,
    isLoading: false,
    login: () => undefined,
    logout: () => undefined,
});

const PUBLIC_PATHS = ['/login'];

function getHomePathByRole(role: string): string {
    const normalized = (role || '').toLowerCase();
    if (normalized === 'director' || normalized === 'editor_chief') return '/';
    if (normalized === 'social_media') return '/editorial';
    return '/news';
}

function readStoredAuth(): { token: string | null; user: AuthUser | null } {
    if (typeof window === 'undefined') {
        return { token: null, user: null };
    }

    const savedToken = window.localStorage.getItem('echorouk_token');
    const savedUser = window.localStorage.getItem('echorouk_user');

    if (!savedToken || !savedUser) {
        return { token: null, user: null };
    }

    try {
        const parsedUser = JSON.parse(savedUser) as AuthUser;
        api.defaults.headers.common.Authorization = `Bearer ${savedToken}`;
        return { token: savedToken, user: parsedUser };
    } catch {
        window.localStorage.removeItem('echorouk_token');
        window.localStorage.removeItem('echorouk_user');
        return { token: null, user: null };
    }
}

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();

    const initial = useMemo(() => readStoredAuth(), []);
    const [user, setUser] = useState<AuthUser | null>(initial.user);
    const [token, setToken] = useState<string | null>(initial.token);

    useEffect(() => {
        if (PUBLIC_PATHS.includes(pathname)) return;
        if (!user) router.push('/login');
    }, [pathname, router, user]);

    const login = (newToken: string, newUser: AuthUser) => {
        window.localStorage.setItem('echorouk_token', newToken);
        window.localStorage.setItem('echorouk_user', JSON.stringify(newUser));
        api.defaults.headers.common.Authorization = `Bearer ${newToken}`;
        setToken(newToken);
        setUser(newUser);
        router.push(getHomePathByRole(newUser.role));
    };

    const logout = async () => {
        try {
            await api.post('/auth/logout');
        } catch {
            // ignore network/logout errors
        }

        window.localStorage.removeItem('echorouk_token');
        window.localStorage.removeItem('echorouk_user');
        delete api.defaults.headers.common.Authorization;
        setToken(null);
        setUser(null);
        router.push('/login');
    };

    return (
        <AuthContext.Provider value={{ user, token, isLoading: false, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}
