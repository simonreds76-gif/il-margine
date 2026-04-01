import Image from "next/image";

type FlagMarkProps = {
  src?: string;
  alt: string;
  fallbackText: string;
  wrapperClassName: string;
  imageClassName: string;
  fallbackClassName: string;
  width: number;
  height: number;
  priority?: boolean;
  sizes?: string;
};

function isSvgUrl(url: string): boolean {
  return /\.svg(?:\?|#|$)/i.test(url);
}

export default function FlagMark({
  src,
  alt,
  fallbackText,
  wrapperClassName,
  imageClassName,
  fallbackClassName,
  width,
  height,
  priority = false,
  sizes,
}: FlagMarkProps) {
  return (
    <div className={wrapperClassName}>
      {src ? (
        isSvgUrl(src) ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={alt}
            width={width}
            height={height}
            loading={priority ? "eager" : "lazy"}
            className={imageClassName}
          />
        ) : (
          <Image
            src={src}
            alt={alt}
            width={width}
            height={height}
            priority={priority}
            sizes={sizes}
            className={imageClassName}
          />
        )
      ) : (
        <span className={fallbackClassName}>{fallbackText}</span>
      )}
    </div>
  );
}
