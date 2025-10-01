"use client";
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const API_URL =
  (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, ""); // strip trailing slash

const isAbsoluteUrl = (u) => /^https?:\/\//i.test(u);

const buildUrl = (raw) => {
  if (!raw) return "";
  return isAbsoluteUrl(raw) ? raw : `${API_URL}/${raw.replace(/^\//, "")}`;
};

// Prefer thumbnail in grid
export const getThumbSrc = (item) =>
  buildUrl(item?.thumbnail_url || item?.image_url || item?.image);

// Prefer preview (or fallback to original) in detail view
export const getDetailSrc = (item) =>
  buildUrl(item?.preview_url || item?.image_url || item?.image);

// Legacy fallback
export const getSrc = (item) => buildUrl(item?.image_url || item?.image);

const Gallery = () => {
  const [images, setImages] = useState([]);
  const [aspectRatios, setAspectRatios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPhoto, setSelectedPhoto] = useState(null);

  const pageVariants = {
    initial: { opacity: 0, x: 50 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -50 },
  };

  useEffect(() => {
    if (!API_URL) {
      console.warn("NEXT_PUBLIC_API_URL is not set");
    }
    fetch(`${API_URL}/api/photos/`)
      .then((r) => r.json())
      .then((data) => {
        // support both {results: [...] } and bare arrays
        const items = Array.isArray(data) ? data : data?.results || [];
        setImages(items);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching photos:", err);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!images.length) return;

    const calc = async () => {
      const ratios = await Promise.all(
        images.map(
          (image) =>
            new Promise((resolve) => {
              const img = new Image();
              // Use the THUMB to measure (lighter)
              img.src = getThumbSrc(image);
              img.onload = () => resolve(img.width / img.height || 1);
              img.onerror = () => resolve(1); // safe fallback
            })
        )
      );
      setAspectRatios(ratios);
    };

    calc();
  }, [images]);

  const handlePhotoClick = (photo) => setSelectedPhoto(photo);
  const handleBackToGallery = () => setSelectedPhoto(null);

  return (
    <div className="justify-items-center mt-4">
      <AnimatePresence>
        {selectedPhoto && (
          <motion.div
            key="photo-detail"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.25 }}
            className="items-center justify-center z-10"
          >
            <button
              onClick={handleBackToGallery}
              className="py-2 px-4 hover:underline underline-offset-4"
            >
              Back to Gallery
            </button>
            <div className="mx-9 mt-5 grid grid-cols-1 md:grid-cols-2">
              <img
                src={getDetailSrc(selectedPhoto)}
                alt={selectedPhoto.title}
                decoding="async"
                className="max-h-[600px] mb-4"
              />
              <div>
                <h2 className="text-2xl font-bold mb-2">
                  {selectedPhoto.title}
                </h2>
                <p className="text-gray-700 dark:text-gray-300 mb-4">
                  {selectedPhoto.description}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {!selectedPhoto && (
        <motion.div
          key="gallery"
          variants={pageVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <div
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mx-20 md:mx-40 pb-11"
            style={{ gridAutoRows: "minmax(200px, auto)" }}
          >
            {loading ? (
              <div>Loading...</div>
            ) : (
              images.map((image, index) => {
                const ratio = aspectRatios[index] || 1;
                const isPortrait = ratio < 1;

                return (
                  <motion.div
                    key={image.id}
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    whileHover={{ scale: 1.05 }}
                    onClick={() => handlePhotoClick(image)}
                    className={`relative bg-gray-200 dark:bg-gray-800 overflow-hidden shadow-lg transition-all duration-300 ease-in-out cursor-pointer ${
                      isPortrait
                        ? "col-span-1 row-span-2"
                        : "col-span-1 row-span-1"
                    }`}
                  >
                    {/* Optional blur-up */}
                    {image.blur_data_url && (
                      <img
                        src={image.blur_data_url}
                        aria-hidden
                        className="absolute inset-0 w-full h-full object-cover blur-md scale-105"
                      />
                    )}
                    <img
                      src={getThumbSrc(image)}
                      alt={image.title}
                      loading="lazy"
                      decoding="async"
                      className="relative w-full object-cover h-full transition-transform duration-300 ease-in-out"
                    />
                  </motion.div>
                );
              })
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default Gallery;
