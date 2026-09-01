import path from "node:path";
import { fileURLToPath } from "node:url";

const isProd = process.env.NODE_ENV === "production";
const repoName = process.env.REPO_NAME || "PhotoPort-V2.0";
const projectRoot = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  outputFileTracingRoot: projectRoot,
  turbopack: { root: projectRoot },
  ...(isProd && repoName ? { basePath: `/${repoName}`, assetPrefix: `/${repoName}/` } : {}),
};

export default nextConfig;
