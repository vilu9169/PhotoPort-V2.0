// frontend/next.config.mjs
const isProd = process.env.NODE_ENV === "production";
const repoName = "PhotoPort-V2.0";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",              // static HTML export (required for GitHub Pages)
  images: { unoptimized: true }, // Next/Image needs this when no server
  trailingSlash: true,           // makes .../page/ -> .../page/index.html
  ...(isProd ? {                 // only add base path on production builds
    basePath: `/${repoName}`,
    assetPrefix: `/${repoName}/`,
  } : {}),
};

export default nextConfig;
