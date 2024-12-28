"use client";
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

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
    // Fetch images from API
    fetch("http://127.0.0.1:8000/api/photos/")
      .then((response) => response.json())
      .then((data) => {
        setImages(data);
        setLoading(false);
      })
      .catch((error) => {
        console.error("Error fetching photos:", error);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    const calculateAspectRatios = async () => {
      const ratios = await Promise.all(
        images.map((image) => {
          const img = new Image();
          img.src = `http://127.0.0.1:8000${image.image}`;
          return new Promise((resolve) => {
            img.onload = () => {
              resolve(img.width / img.height);
            };
          });
        })
      );
      setAspectRatios(ratios);
    };

    if (images.length > 0) {
      calculateAspectRatios();
    }
  }, [images]);

  const handlePhotoClick = (photo) => {
    setSelectedPhoto(photo);
  };

  const handleBackToGallery = () => {
    setSelectedPhoto(null);
  };

  return (
    <div className="justify-items-center mt-4">
      <AnimatePresence>
        {/* Detail View */}
        {selectedPhoto && (
          <motion.div
            key="photo-detail"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.25 }}
            className=" items-center justify-center z-10"
          >
                <button
                onClick={handleBackToGallery}
                className=" py-2 px-4 hover:underline underline-offset-4"
              >
                Back to Gallery
              </button>
            <div className=" mx-9 mt-5 grid grid-cols-1 md:grid-cols-2">
              <img
                src={`http://127.0.0.1:8000${selectedPhoto.image}`}
                alt={selectedPhoto.title}
                className=" max-h-[600px] mb-4"
              />
              <div>
              <h2 className="text-2xl font-bold mb-2">{selectedPhoto.title}</h2>
              <p className="text-gray-700 dark:text-gray-300 mb-4">
                {selectedPhoto.description}
              </p>
              </div>
            </div>
            </motion.div>
        )}
      </AnimatePresence>

      {/* Gallery View */}
      {!selectedPhoto && (
        <motion.div
        key="gallery"
        variants={pageVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={{ duration: 0.5, delay: 0.30   }}
      >
        <div
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mx-20 md:mx-40 pb-11"
          style={{ gridAutoRows: "minmax(200px, auto)" }}
        >
          {loading ? (
            <div>Loading...</div>
          ) : (
            images.map((image, index) => {
              const aspectRatio = aspectRatios[index];
              const isPortrait = aspectRatio < 1;

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
                    isPortrait ? "col-span-1 row-span-2" : "col-span-1 row-span-1"
                  }`}
                >
                  <img
                    src={`http://127.0.0.1:8000${image.image}`}
                    alt={image.title}
                    className="w-full object-cover h-full transition-transform duration-300 ease-in-out"
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
