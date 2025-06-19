import axios, { AxiosInstance, AxiosError } from "axios";

// Types
export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
  updated_at: string;
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
  id: string;
  name: string;
  description?: string;
  is_private: boolean;
  created_by: string;
  member_count?: number;
  created_at: string;
  updated_at: string;
}

export interface CreateGroupRequest {
  name: string;
  description?: string;
  is_private: boolean;
}

export interface Meeting {
  id: string;
  group_id: string;
  title?: string;
  description?: string;
  start_time: string;
  end_time: string;
  meeting_date: string;
  track_gps?: string; // WKT string representation
  bbox_north?: number;
  bbox_south?: number;
  bbox_east?: number;
  bbox_west?: number;
  photo_count: number;
  participant_count: number;
  created_at: string;
  updated_at?: string;
  cover_photo_id?: string;
}

export interface Photo {
  id: string;
  group_id: string;
  uploader_id: string;
  meeting_id?: string;
  filename_orig: string;
  filename_thumb?: string;
  filename_medium?: string;
  file_size: number;
  file_hash: string;
  mime_type: string;
  shot_at?: string;
  camera_make?: string;
  camera_model?: string;
  lens_model?: string;
  width?: number;
  height?: number;
  orientation?: number;
  aperture?: number;
  shutter_speed?: string;
  iso?: number;
  focal_length?: number;
  flash?: boolean;
  point_gps?: any; // PostGIS geometry
  gps_altitude?: number;
  gps_accuracy?: number;
  exif_data?: Record<string, any>;
  caption?: string;
  tags?: string;
  is_processed: boolean;
  processing_error?: string;
  uploaded_at: string;
  updated_at?: string;
  is_public: boolean;
  is_flagged: boolean;
  flagged_reason?: string;
}

export interface PhotoUploadResponse {
  id: string;
  filename: string;
  status: string;
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
  photoById: (id: string) => `/photos/${id}`,
  photoThumb: (id: string) => `/photos/${id}/thumb`,

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
