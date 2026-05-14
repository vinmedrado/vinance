import axios from 'axios';

const baseURL = import.meta.env.VITE_API_URL || '/api';
export const api = axios.create({ baseURL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('financeos_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export async function login(email: string, password: string) {
  const { data } = await api.post('/auth/login', { email, password });
  localStorage.setItem('financeos_token', data.access_token);
  return data;
}

export function logout() {
  localStorage.removeItem('financeos_token');
}
