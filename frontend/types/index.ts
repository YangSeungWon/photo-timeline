// Core Types
export interface ApiError {
  detail: string;
  status_code?: number;
}

// User Types
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

export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// Group Types
export interface Group {
  id: string;
  name: string;
  description?: string;
  is_private: boolean;
  created_by: string;
  created_at: string;
  updated_at?: string;
  member_count?: number;
}

export interface CreateGroupRequest {
  name: string;
  description?: string;
  is_private: boolean;
}

export interface GroupJoinRequest {
  // Add any fields needed for joining groups
}

// Meeting Types
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

export interface CreateMeetingRequest {
  title?: string;
  description?: string;
  start_time: string;
  end_time: string;
}

// Photo Types
export interface Photo {
  id: string;
  group_id: string;
  uploader_id: string;
  meeting_id?: string;
  filename_orig: string;
  filename_thumb?: string;
  file_size: number;
  file_hash: string;
  mime_type: string;
  width?: number;
  height?: number;
  datetime_taken?: string;
  point_gps?: string; // WKT Point
  altitude?: number;
  camera_make?: string;
  camera_model?: string;
  camera_settings?: string;
  is_processed: boolean;
  created_at: string;
  updated_at?: string;
}

export interface PhotoUploadResponse {
  id: string;
  filename: string;
  status: string;
  message: string;
}

// UI Component Types
export interface ModalProps {
  isOpen?: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit' | 'reset';
  className?: string;
}

export interface CardProps {
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

// Form Types
export interface FormInputProps {
  id: string;
  name: string;
  type?: string;
  label?: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  required?: boolean;
  disabled?: boolean;
}

export interface FormTextareaProps {
  id: string;
  name: string;
  label?: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  rows?: number;
}

// Utility Types
export interface PaginationParams {
  page: number;
  limit: number;
  total?: number;
}

export interface SortParams {
  field: string;
  direction: 'asc' | 'desc';
}

export interface FilterParams {
  [key: string]: string | number | boolean | undefined;
} 