const isProd = process.env.NODE_ENV === "production";
const repoName = process.env.REPO_NAME || "PhotoPort-V2.0";

/** @type {import('next').NextConfig} */
export default {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  ...(isProd && repoName ? { basePath: `/${repoName}`, assetPrefix: `/${repoName}/` } : {}),
};
