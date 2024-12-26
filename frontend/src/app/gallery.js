"use client";
import React, { useEffect, useState } from "react";

const Gallery = () => {
  const [images, setImages] = useState([]);
  const [aspectRatios, setAspectRatios] = useState([]);
  const [loading, setLoading] = useState(true);

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

  return (
    <div className="justify-items-center mt-4">
      {loading ? (
        <div>Loading...</div>
      ) : (
        <div
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mx-20 md:mx-40 pb-11"
          style={{ gridAutoRows: "minmax(200px, auto)" }}
        >
          {images.map((image, index) => {
            const aspectRatio = aspectRatios[index];
            const isPortrait = aspectRatio < 1;

            return (
              <div
                key={image.id}
                className={`relative bg-gray-200 dark:bg-gray-800 overflow-hidden shadow-lg transition-all duration-300 ease-in-out ${
                  isPortrait ? "col-span-1 row-span-2" : "col-span-1 row-span-1"
                }`}
              >
                <img
                  src={`http://127.0.0.1:8000${image.image}`}
                  alt={image.title}
                  className="w-full object-cover h-full transition-transform duration-300 ease-in-out"
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Gallery;
