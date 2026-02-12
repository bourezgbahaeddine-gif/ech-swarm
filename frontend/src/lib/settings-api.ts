import { api } from '@/lib/api';

export const settingsApi = {
    list: () => api.get('/settings/'),
    upsert: (key: string, data: { value?: string; is_secret?: boolean; description?: string }) =>
        api.put(`/settings/${key}`, data),
    importEnv: () => api.post('/settings/import-env'),
    test: (key: string) => api.get(`/settings/test/${key}`),
    audit: (limit = 200) => api.get(`/settings/audit?limit=${limit}`),
};
