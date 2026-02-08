import axios from "axios";

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://ac5bdde4e617d40babf46317fe4ba7bd-908634635.us-east-1.elb.amazonaws.com",
});


