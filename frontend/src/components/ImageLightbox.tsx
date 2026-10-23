import { useEffect, useRef, useState } from "react";

interface Props {
  images: { file_url: string }[];
  startIndex: number;
  onClose: () => void;
}

const MIN_SCALE = 1;
const MAX_SCALE = 4;

export default function ImageLightbox({ images, startIndex, onClose }: Props) {
  const [index, setIndex] = useState(startIndex);
  const [scale, setScale] = useState(MIN_SCALE);
  const [translate, setTranslate] = useState({ x: 0, y: 0 });
  const dragState = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null);

  useEffect(() => {
    setScale(MIN_SCALE);
    setTranslate({ x: 0, y: 0 });
  }, [index]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") setIndex((i) => Math.max(0, i - 1));
      if (e.key === "ArrowRight") setIndex((i) => Math.min(images.length - 1, i + 1));
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [images.length, onClose]);

  function handleWheel(e: React.WheelEvent) {
    e.preventDefault();
    setScale((s) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s - e.deltaY * 0.01)));
  }

  function handleDoubleClick() {
    setScale((s) => (s > MIN_SCALE ? MIN_SCALE : 2));
    setTranslate({ x: 0, y: 0 });
  }

  function handleMouseDown(e: React.MouseEvent) {
    if (scale <= MIN_SCALE) return;
    dragState.current = {
      startX: e.clientX,
      startY: e.clientY,
      originX: translate.x,
      originY: translate.y,
    };
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!dragState.current) return;
    const dx = e.clientX - dragState.current.startX;
    const dy = e.clientY - dragState.current.startY;
    setTranslate({ x: dragState.current.originX + dx, y: dragState.current.originY + dy });
  }

  function handleMouseUp() {
    dragState.current = null;
  }

  const canGoPrev = index > 0;
  const canGoNext = index < images.length - 1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <button
        onClick={onClose}
        aria-label="Close"
        className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-2xl text-white hover:bg-white/20"
      >
        ×
      </button>

      {canGoPrev && (
        <button
          onClick={() => setIndex((i) => i - 1)}
          aria-label="Previous image"
          className="absolute left-4 flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-2xl text-white hover:bg-white/20"
        >
          ←
        </button>
      )}

      <div
        className="max-h-full max-w-full overflow-hidden"
        onWheel={handleWheel}
        onDoubleClick={handleDoubleClick}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <img
          src={images[index].file_url}
          alt={`Prescription image ${index + 1} of ${images.length}`}
          className="max-h-[90vh] max-w-[90vw] select-none object-contain"
          style={{
            transform: `scale(${scale}) translate(${translate.x / scale}px, ${translate.y / scale}px)`,
            cursor: scale > MIN_SCALE ? "grab" : "zoom-in",
          }}
          draggable={false}
        />
      </div>

      {canGoNext && (
        <button
          onClick={() => setIndex((i) => i + 1)}
          aria-label="Next image"
          className="absolute right-20 flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-2xl text-white hover:bg-white/20"
        >
          →
        </button>
      )}

      <p className="absolute bottom-4 text-sm text-white/70">
        {index + 1} / {images.length}
      </p>
    </div>
  );
}
