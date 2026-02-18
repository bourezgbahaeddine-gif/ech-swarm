import { api } from '@/lib/api';

export const constitutionApi = {
    latest: () => api.get('/constitution/latest'),
    ackStatus: () => api.get('/constitution/ack'),
    acknowledge: (version: string) => api.post('/constitution/ack', { version }),
    tips: () => api.get('/constitution/tips'),
    guide: () => api.get('/constitution/guide'),
};
