import { authenticatedApi } from "./api";

// SWR fetcher for authenticated requests
export const authenticatedFetcher = (token: string) => {
  return async (url: string) => {
    const response = await authenticatedApi(token).get(url);
    return response.data;
  };
};
