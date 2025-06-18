import axios, { AxiosInstance, AxiosError } from "axios";

// Types
export interface User {
  id: number;
  email: string;
  full_name?: string;
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserRegister {
  email: string;
  password: string;
  display_name: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
}

export interface Group {
  id: number;
  name: string;
  description?: string;
  is_public: boolean;
  member_count?: number;
  created_at: string;
}

export interface CreateGroupRequest {
  name: string;
  description?: string;
  is_public: boolean;
}

export interface Meeting {
  id: number;
  name: string;
  description?: string;
  date: string;
  group_id: number;
  created_at: string;
}

export interface Photo {
  id: number;
  filename_orig: string;
  file_size: number;
  taken_at?: string;
  latitude?: number;
  longitude?: number;
  meeting_id?: number;
  uploaded_by: number;
  created_at: string;
}

export interface PhotoUploadResponse {
  id: number;
  filename_orig: string;
  message: string;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}

// Base axios instance
export const api = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

// Authenticated axios instance
export const authenticatedApi = (token: string): AxiosInstance => {
  return axios.create({
    baseURL: "/api/v1",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  });
};

// Endpoints
export const endpoints = {
  // Auth
  login: "/auth/login",
  register: "/auth/register",
  verifyEmail: "/auth/verify-email",
  resendVerification: "/auth/resend-verification",
  me: "/auth/me",
  refresh: "/auth/refresh",

  // Groups
  groups: "/groups",
  groupById: (id: string) => `/groups/${id}`,

  // Photos
  photos: "/photos",
  photosUpload: "/photos/upload",
  photoById: (id: number) => `/photos/${id}`,
  photoThumb: (id: number) => `/photos/${id}/thumb`,

  // Meetings
  meetings: "/meetings",
  meetingById: (id: string) => `/meetings/${id}`,
};

// Error handler
export const handleApiError = (error: unknown): ApiError => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiError>;
    if (axiosError.response?.data) {
      return {
        detail: axiosError.response.data.detail || "An error occurred",
        status_code: axiosError.response.status,
      };
    }
    return {
      detail: axiosError.message || "Network error",
      status_code: axiosError.response?.status,
    };
  }
  return {
    detail: "An unexpected error occurred",
  };
};
