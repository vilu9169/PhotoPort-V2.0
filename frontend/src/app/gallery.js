"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { createPortal } from "react-dom";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
const GALLERY_TEXTURE =
  process.env.NODE_ENV === "production"
    ? "/PhotoPort-V2.0/gallery-texture.png"
    : "/gallery-texture.png";

const isAbsoluteUrl = (url) => /^https?:\/\//i.test(url);

const buildUrl = (raw) => {
  if (!raw) return "";
  return isAbsoluteUrl(raw) ? raw : `${API_URL}/${raw.replace(/^\//, "")}`;
};

export const getThumbSrc = (item) =>
  buildUrl(item?.thumbnail_url || item?.image_url || item?.image);

export const getDetailSrc = (item) =>
  buildUrl(item?.preview_url || item?.image_url || item?.image);

export const getSrc = (item) => buildUrl(item?.image_url || item?.image);

const getPathCollectionSlug = (photo) => {
  const rawPath =
    photo.image_url || photo.thumbnail_url || photo.preview_url || photo.image || "";
  const match = rawPath.match(/\/photos\/([^/]+)\//i);
  const candidate = match?.[1]?.toLowerCase();

  if (!candidate || /^\d{4}$/.test(candidate)) return "";
  return candidate;
};

const titleFromSlug = (slug) =>
  slug
    .split("-")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

const getCollectionKey = (photo) =>
  photo.label_slug ||
  photo.folder_slug ||
  getPathCollectionSlug(photo) ||
  (photo.category || "unsorted").toLowerCase().replace(/\s+/g, "-");

const formatCollectionName = (photo) => {
  if (photo.label_title) return photo.label_title;
  if (photo.folder_title) return photo.folder_title;
  if (photo.category) return photo.category;

  const pathSlug = getPathCollectionSlug(photo);
  return pathSlug ? titleFromSlug(pathSlug) : "Unsorted";
};

const getPhotoDate = (value) => {
  if (!value) return "";
  return new Intl.DateTimeFormat("en", { year: "numeric" }).format(new Date(value));
};

function ArrowIcon({ direction = "right" }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={direction === "left" ? "rotate-180" : ""}
    >
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M5 5l14 14M19 5 5 19" />
    </svg>
  );
}

function PhotoCard({ photo, index, onSelect }) {
  const [loaded, setLoaded] = useState(false);

  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-8%" }}
      transition={{ duration: 0.55, delay: Math.min(index * 0.035, 0.25) }}
      className="gallery-card"
      onClick={() => onSelect(photo)}
      aria-label={`Open ${photo.title || "photograph"}`}
    >
      <img
        src={getThumbSrc(photo)}
        alt={photo.title || formatCollectionName(photo)}
        loading="lazy"
        decoding="async"
        onLoad={() => setLoaded(true)}
        className={`gallery-card__image ${loaded ? "is-loaded" : ""}`}
      />
      <span className="gallery-card__shade" aria-hidden="true" />
      <span className="gallery-card__meta">
        <span>{photo.title || "Untitled"}</span>
        <span className="gallery-card__open">
          View <ArrowIcon />
        </span>
      </span>
    </motion.button>
  );
}

function PhotoViewer({ photo, photos, onClose, onChange }) {
  const closeButtonRef = useRef(null);
  const index = photos.findIndex((item) => item.id === photo.id);
  const canNavigate = photos.length > 1;

  const navigate = useCallback(
    (direction) => {
      if (!canNavigate) return;
      const nextIndex = (index + direction + photos.length) % photos.length;
      onChange(photos[nextIndex]);
    },
    [canNavigate, index, onChange, photos]
  );

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    const handleKeyDown = (event) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowRight") navigate(1);
      if (event.key === "ArrowLeft") navigate(-1);
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [navigate, onClose]);

  useEffect(() => {
    if (!canNavigate) return;
    [-1, 1].forEach((direction) => {
      const adjacent =
        photos[(index + direction + photos.length) % photos.length];
      const image = new Image();
      image.src = getDetailSrc(adjacent);
    });
  }, [canNavigate, index, photos]);

  return (
    <motion.div
      className="photo-viewer"
      role="dialog"
      aria-modal="true"
      aria-label={photo.title || "Photo viewer"}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <button
        ref={closeButtonRef}
        type="button"
        className="photo-viewer__close"
        onClick={onClose}
        aria-label="Close photo viewer"
      >
        <CloseIcon />
        <span>Close</span>
      </button>

      {canNavigate && (
        <>
          <button
            type="button"
            className="photo-viewer__arrow photo-viewer__arrow--left"
            onClick={() => navigate(-1)}
            aria-label="Previous photograph"
          >
            <ArrowIcon direction="left" />
          </button>
          <button
            type="button"
            className="photo-viewer__arrow photo-viewer__arrow--right"
            onClick={() => navigate(1)}
            aria-label="Next photograph"
          >
            <ArrowIcon />
          </button>
        </>
      )}

      <div className="photo-viewer__layout">
        <motion.div
          className="photo-viewer__stage"
          key={photo.id}
          initial={{ opacity: 0, scale: 0.985 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.35 }}
          drag={canNavigate ? "x" : false}
          dragConstraints={{ left: 0, right: 0 }}
          dragElastic={0.08}
          onDragEnd={(_, info) => {
            if (info.offset.x > 70) navigate(-1);
            if (info.offset.x < -70) navigate(1);
          }}
        >
          <img
            src={getDetailSrc(photo)}
            alt={photo.title || formatCollectionName(photo)}
            decoding="async"
          />
        </motion.div>

        <motion.aside
          className="photo-viewer__details"
          key={`details-${photo.id}`}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.08 }}
        >
          <div className="photo-viewer__eyebrow">
            <span>{formatCollectionName(photo)}</span>
            <span>
              {String(index + 1).padStart(2, "0")} /{" "}
              {String(photos.length).padStart(2, "0")}
            </span>
          </div>
          <h2>{photo.title || "Untitled"}</h2>
          {photo.description && <p>{photo.description}</p>}
          <div className="photo-viewer__footer">
            <span>{getPhotoDate(photo.created_at)}</span>
            <span>Use arrow keys or swipe</span>
          </div>
        </motion.aside>
      </div>
    </motion.div>
  );
}

const Gallery = () => {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeCollection, setActiveCollection] = useState("all");
  const [selectedPhoto, setSelectedPhoto] = useState(null);

  useEffect(() => {
    if (!API_URL) {
      setError("The photo service is not configured.");
      setLoading(false);
      return;
    }

    fetch(`${API_URL}/api/photos/?limit=200`)
      .then(async (response) => {
        const contentType = response.headers.get("content-type") || "";
        if (!response.ok) {
          throw new Error(`Photo API returned HTTP ${response.status}`);
        }
        if (!contentType.includes("application/json")) {
          throw new Error("Photo API returned a non-JSON response");
        }
        return response.json();
      })
      .then((data) => {
        setImages(Array.isArray(data) ? data : data?.results || []);
        setLoading(false);
      })
      .catch((fetchError) => {
        console.error("Error fetching photos:", fetchError);
        setError("The photo service is temporarily unavailable.");
        setLoading(false);
      });
  }, []);

  const collections = useMemo(() => {
    const grouped = new Map();

    images.forEach((photo) => {
      const key = getCollectionKey(photo);
      if (!grouped.has(key)) {
        grouped.set(key, {
          key,
          title: formatCollectionName(photo),
          order: photo.label_order ?? photo.folder_order ?? -1,
          photos: [],
        });
      }
      grouped.get(key).photos.push(photo);
    });

    return [...grouped.values()].sort(
      (a, b) => b.order - a.order || a.title.localeCompare(b.title)
    );
  }, [images]);

  const visibleCollections = useMemo(
    () =>
      activeCollection === "all"
        ? collections
        : collections.filter((collection) => collection.key === activeCollection),
    [activeCollection, collections]
  );

  const viewerPhotos = useMemo(
    () => visibleCollections.flatMap((collection) => collection.photos),
    [visibleCollections]
  );

  return (
    <section
      className="gallery-shell"
      style={{ "--gallery-texture": `url(${GALLERY_TEXTURE})` }}
    >
      <header className="gallery-intro">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <p className="gallery-kicker">Selected photography</p>
          <h1>Places, people, and moments in between.</h1>
        </motion.div>
        <motion.p
          className="gallery-intro__copy"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
        >
          A visual journal from cities and landscapes across Asia and Sweden.
          Choose a collection or wander through the complete archive.
        </motion.p>
      </header>

      {!loading && !error && (
        <nav className="collection-nav" aria-label="Photo collections">
          <button
            type="button"
            className={activeCollection === "all" ? "is-active" : ""}
            onClick={() => setActiveCollection("all")}
          >
            <span>All work</span>
            <small>{images.length}</small>
          </button>
          {collections.map((collection) => (
            <button
              type="button"
              key={collection.key}
              className={activeCollection === collection.key ? "is-active" : ""}
              onClick={() => setActiveCollection(collection.key)}
            >
              <span>{collection.title}</span>
              <small>{collection.photos.length}</small>
            </button>
          ))}
        </nav>
      )}

      {loading && (
        <div className="gallery-status" role="status">
          <span className="gallery-status__line" />
          <p>Developing photographs...</p>
        </div>
      )}

      {error && (
        <div className="gallery-status gallery-status--error" role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => window.location.reload()}>
            Try again
          </button>
        </div>
      )}

      {!loading && !error && (
        <AnimatePresence mode="popLayout">
          <motion.div
            key={activeCollection}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="collection-list"
          >
            {visibleCollections.map((collection) => (
              <section className="collection" key={collection.key}>
                <div className="collection__heading">
                  <div>
                    <p>Collection</p>
                    <h2>{collection.title}</h2>
                  </div>
                  <span>
                    {String(collection.photos.length).padStart(2, "0")} photographs
                  </span>
                </div>

                <div className="gallery-grid">
                  {collection.photos.map((photo, index) => (
                    <PhotoCard
                      key={photo.id}
                      photo={photo}
                      index={index}
                      onSelect={setSelectedPhoto}
                    />
                  ))}
                </div>
              </section>
            ))}
          </motion.div>
        </AnimatePresence>
      )}

      {typeof document !== "undefined" &&
        createPortal(
          <AnimatePresence>
            {selectedPhoto && (
              <PhotoViewer
                photo={selectedPhoto}
                photos={viewerPhotos}
                onClose={() => setSelectedPhoto(null)}
                onChange={setSelectedPhoto}
              />
            )}
          </AnimatePresence>,
          document.body
        )}
    </section>
  );
};

export default Gallery;
