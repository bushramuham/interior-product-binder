"""Data models shared across the binder pipeline."""

from dataclasses import dataclass, field


@dataclass
class ProductEntry:
    """One row of the Excel schedule."""

    key: str
    description: str = ""
    description2: str = ""
    description3: str = ""
    raw_path: str = ""
    page_hint: str = ""


@dataclass
class Product:
    """One group of schedule rows sharing the same source (= one binder section)."""

    group_id: str
    source_path: str
    source_type: str  # "pdf" | "url" | "unknown"
    entries: list[ProductEntry] = field(default_factory=list)

    @property
    def keys(self) -> list[str]:
        return [e.key for e in self.entries]

    @property
    def combined_description(self) -> str:
        parts = []
        for e in self.entries:
            for text in (e.description, e.description2, e.description3):
                if text and text not in parts:
                    parts.append(text)
        return " | ".join(parts)


@dataclass
class ExtractedContent:
    """Result of extracting a single source (PDF or URL)."""

    text: str = ""
    image_paths: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ProductInfo:
    """Structured product information returned by the AI model."""

    product_name: str = ""
    manufacturer: str = ""
    description: str = ""
    dimensions: str = ""
    materials: str = ""
    finishes: str = ""
    certifications: str = ""
    installation_notes: str = ""
    care_notes: str = ""
    important_specs: list[str] = field(default_factory=list)


@dataclass
class ProductResult:
    """Everything the PDF builder needs to render one product section."""

    product: Product
    info: ProductInfo | None = None
    representative_image: str | None = None
    error: str | None = None
