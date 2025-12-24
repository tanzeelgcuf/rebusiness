
import { GoogleGenAI, Type } from "@google/genai";
import { Wholesaler, Solicitation, TechnicalSpec } from "./types";

export class GeminiService {
  private ai: GoogleGenAI;

  constructor() {
    this.ai = new GoogleGenAI({ apiKey: process.env.API_KEY as string });
  }

  /**
   * Helper to handle retries with exponential backoff
   */
  private async callWithRetry<T>(fn: () => Promise<T>, retries = 5, delay = 5000): Promise<T> {
    try {
      return await fn();
    } catch (error: any) {
      const errStr = JSON.stringify(error).toLowerCase();
      const isRateLimit = errStr.includes('429') || 
                          errStr.includes('quota') || 
                          errStr.includes('exhausted') ||
                          error?.message?.toLowerCase().includes('quota');

      if (isRateLimit && retries > 0) {
        const jitter = Math.random() * 1000;
        const waitTime = delay + jitter;
        console.warn(`Quota limit hit. Sleeping for ${Math.round(waitTime/1000)}s before retry... (${retries} left)`);
        await new Promise(resolve => setTimeout(resolve, waitTime));
        return this.callWithRetry(fn, retries - 1, Math.min(delay * 2, 30000));
      }
      throw error;
    }
  }

  /**
   * Stage 1: Autonomous SAM.gov Discovery with Link Mapping
   */
  async crawlSamGov(query: string): Promise<Solicitation[]> {
    return this.callWithRetry(async () => {
      const prompt = `Act as an expert federal procurement agent. 
      Target: Search SAM.gov for solicitations matching "${query}".
      
      CRITICAL INSTRUCTION: Analyze the description for any nested links, attachment references (PDF/DOCX/Excel), or external procurement portals (DLA, GSA, Agency-specific sites). 
      Return the results as JSON.`;

      const response = await this.ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: prompt,
        config: {
          tools: [{ googleSearch: {} }],
          responseMimeType: "application/json",
          responseSchema: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                title: { type: Type.STRING },
                agency: { type: Type.STRING },
                url: { type: Type.STRING },
                description: { type: Type.STRING },
                postedDate: { type: Type.STRING },
                nested_links: { type: Type.ARRAY, items: { type: Type.STRING }, description: "Links found inside the description or portal references." }
              },
              required: ["title", "agency", "url", "description", "postedDate", "nested_links"]
            }
          }
        }
      });

      const data = JSON.parse(response.text || "[]");
      return data.map((item: any) => ({
        ...item,
        id: `SAM-${Math.random().toString(36).substr(2, 5).toUpperCase()}`
      }));
    });
  }

  /**
   * Stage 2: Deep Spec Extraction (Crawl nested portals)
   */
  async extractDeepSpecs(solicitation: Solicitation): Promise<TechnicalSpec> {
    return this.callWithRetry(async () => {
      const linksToFollow = solicitation.nested_links?.join(", ") || solicitation.url;
      const prompt = `Perform a deep technical analysis of this procurement.
      Sources to examine: ${linksToFollow}
      Original Solicitation: ${solicitation.title} - ${solicitation.description}
      
      INSTRUCTION: Use Google Search to find the actual content of the linked documents or portals. 
      Identify specific Manufacturer Part Numbers (MPNs), NSNs, quantities, and material requirements buried in the attachments or linked sites.`;

      const response = await this.ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: prompt,
        config: {
          tools: [{ googleSearch: {} }],
          responseMimeType: "application/json",
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              quantity: { type: Type.STRING },
              size: { type: Type.STRING },
              material: { type: Type.STRING },
              attachments_found: { type: Type.ARRAY, items: { type: Type.STRING } },
              manufacturing_synonyms: { type: Type.ARRAY, items: { type: Type.STRING } },
              product_complexity: { type: Type.STRING, enum: ["low", "medium", "high"] }
            },
            required: ["quantity", "size", "material", "attachments_found", "manufacturing_synonyms", "product_complexity"]
          }
        }
      });

      return JSON.parse(response.text || "{}");
    });
  }

  /**
   * Stage 3: Thomasnet High-Level Sourcing (Accuracy focus)
   */
  async sourceFromThomasnet(specs: TechnicalSpec, productType: string): Promise<Wholesaler[]> {
    return this.callWithRetry(async () => {
      const searchKeywords = [productType, ...specs.manufacturing_synonyms].join(", ");
      const prompt = `Identify 40 high-accuracy wholesalers for "${productType}" on Thomasnet and medical directories.
      Requirements from Deep Crawl: ${specs.material}, ${specs.size}, ${specs.quantity}.
      
      ACCURACY PROTOCOL:
      - Verification Confidence must be > 90%.
      - Only include firms whose online catalogs or Thomasnet profiles explicitly list these medical instruments.
      - Emails MUST be direct corporate contacts (e.g., sales@ or procurement@).
      
      Return as JSON array.`;

      const response = await this.ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: prompt,
        config: {
          tools: [{ googleSearch: {} }],
          responseMimeType: "application/json",
          responseSchema: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                name: { type: Type.STRING },
                location: { type: Type.STRING },
                email: { type: Type.STRING },
                website: { type: Type.STRING },
                specialty: { type: Type.STRING },
                confidence: { type: Type.NUMBER }
              },
              required: ["name", "location", "email", "website", "specialty", "confidence"]
            }
          }
        }
      });

      const data = JSON.parse(response.text || "[]");
      return data.map((w: any) => ({
        ...w,
        id: `WH-${Math.random().toString(36).substr(2, 5).toUpperCase()}`
      }));
    });
  }

  /**
   * Expands category for 500+ goal
   */
  async expandCategory(category: string): Promise<string[]> {
    return this.callWithRetry(async () => {
      const prompt = `Niche down "${category}" into 15 industrial medical instrument sub-categories. JSON Array.`;
      const response = await this.ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: prompt,
        config: {
          responseMimeType: "application/json",
          responseSchema: { type: Type.ARRAY, items: { type: Type.STRING } }
        }
      });
      return JSON.parse(response.text || "[]");
    });
  }
}
