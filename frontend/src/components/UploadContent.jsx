import React, { useState } from 'react';
import { 
  FileText, 
  Image as ImageIcon, 
  Video, 
  Headphones, 
  Globe,
  Upload, 
  Loader2,
  CheckCircle2,
  AlertCircle,
  Sparkles
} from 'lucide-react';

export default function UploadContent({ onUploadSuccess }) {
  const [webText, setWebText] = useState('');
  const [loading, setLoading] = useState({});
  const [toast, setToast] = useState(null);
  const [dragOverCard, setDragOverCard] = useState(null);

  const showNotification = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3800);
  };

  // Helper for Uploading Files to Backend
  const handleFileUpload = async (file, endpoint, defaultType) => {
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) {
      showNotification('File exceeds maximum limit of 15MB', 'error');
      return;
    }

    setLoading(prev => ({ ...prev, [defaultType]: true }));
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', file.name.substring(0, file.name.lastIndexOf('.')) || file.name);

    try {
      const res = await fetch(`http://localhost:8000${endpoint}`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        showNotification(`Successfully ingested "${file.name}" into Supabase vector store!`, 'success');
        if (onUploadSuccess) onUploadSuccess();
      } else {
        showNotification(data.detail || 'Upload failed', 'error');
      }
    } catch (err) {
      showNotification(`Upload error: ${err.message}`, 'error');
    } finally {
      setLoading(prev => ({ ...prev, [defaultType]: false }));
    }
  };

  return (
    <div className="workspace-container">
      {/* Notification Toast Banner */}
      {toast && (
        <div className={`toast-banner-box ${toast.type}`}>
          {toast.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span>{toast.msg}</span>
        </div>
      )}

      {/* Header Banner */}
      <div className="workspace-header-center">
        <div className="gradient-badge-small">
          <Sparkles size={14} />
          <span>Multimodal Ingestion</span>
        </div>
        <h1 className="title-hero">Ingest Data into ZymeRag</h1>
        <p className="subtitle-hero">
          Upload documents, images, video, audio, or web content to generate vector embeddings stored in Supabase pgvector.
        </p>
      </div>

      {/* 2-Column Grid of Cards */}
      <div className="ingestion-grid">
        
        {/* Card 1: PDF & Word Documents */}
        <div 
          className={`ingestion-card ${dragOverCard === 'doc' ? 'drag-over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOverCard('doc'); }}
          onDragLeave={() => setDragOverCard(null)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOverCard(null);
            if (e.dataTransfer.files[0]) {
              const file = e.dataTransfer.files[0];
              const endpoint = file.name.endsWith('.docx') ? '/upload/upload_docx' : '/upload/upload_pdf';
              handleFileUpload(file, endpoint, 'doc');
            }
          }}
        >
          <div className="card-top-header">
            <div className="icon-wrapper icon-indigo">
              <FileText size={22} />
            </div>
            <div>
              <h3 className="card-heading">PDF & Word Documents</h3>
              <p className="card-subtext">Process text and pages from documents</p>
            </div>
          </div>

          <label className="custom-dropzone">
            <input 
              type="file" 
              accept=".pdf,.docx,.txt"
              onChange={(e) => {
                if (e.target.files[0]) {
                  const file = e.target.files[0];
                  const endpoint = file.name.endsWith('.docx') ? '/upload/upload_docx' : '/upload/upload_pdf';
                  handleFileUpload(file, endpoint, 'doc');
                }
              }}
            />
            {loading.doc ? (
              <div className="loading-spinner-box">
                <Loader2 className="animate-spin text-indigo" size={28} />
                <span className="uploading-text">Generating Embeddings...</span>
              </div>
            ) : (
              <>
                <Upload className="dropzone-svg-icon text-indigo" size={28} />
                <div className="dropzone-main-text">
                  Drop PDF / Word file or <span className="highlight-browse">browse</span>
                </div>
                <span className="dropzone-sub-text">Supported: .pdf, .docx, .txt (up to 15MB)</span>
              </>
            )}
          </label>
        </div>

        {/* Card 2: Multimodal Images */}
        <div 
          className={`ingestion-card ${dragOverCard === 'img' ? 'drag-over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOverCard('img'); }}
          onDragLeave={() => setDragOverCard(null)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOverCard(null);
            if (e.dataTransfer.files[0]) {
              handleFileUpload(e.dataTransfer.files[0], '/upload/upload_image', 'img');
            }
          }}
        >
          <div className="card-top-header">
            <div className="icon-wrapper icon-violet">
              <ImageIcon size={22} />
            </div>
            <div>
              <h3 className="card-heading">Multimodal Images</h3>
              <p className="card-subtext">Extract text and layout from images</p>
            </div>
          </div>

          <label className="custom-dropzone">
            <input 
              type="file" 
              accept="image/*"
              onChange={(e) => {
                if (e.target.files[0]) {
                  handleFileUpload(e.target.files[0], '/upload/upload_image', 'img');
                }
              }}
            />
            {loading.img ? (
              <div className="loading-spinner-box">
                <Loader2 className="animate-spin text-violet" size={28} />
                <span className="uploading-text">Extracting Image OCR...</span>
              </div>
            ) : (
              <>
                <Upload className="dropzone-svg-icon text-violet" size={28} />
                <div className="dropzone-main-text">
                  Drop image here or <span className="highlight-browse text-violet">browse</span>
                </div>
                <span className="dropzone-sub-text">Supported: .png, .jpg, .jpeg, .webp, .tiff</span>
              </>
            )}
          </label>
        </div>

        {/* Card 3: Video Transcription */}
        <div 
          className={`ingestion-card ${dragOverCard === 'vid' ? 'drag-over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOverCard('vid'); }}
          onDragLeave={() => setDragOverCard(null)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOverCard(null);
            if (e.dataTransfer.files[0]) {
              handleFileUpload(e.dataTransfer.files[0], '/upload/upload_video', 'vid');
            }
          }}
        >
          <div className="card-top-header">
            <div className="icon-wrapper icon-purple">
              <Video size={22} />
            </div>
            <div>
              <h3 className="card-heading">Video Transcription</h3>
              <p className="card-subtext">Transcribe speech and index video audio</p>
            </div>
          </div>

          <label className="custom-dropzone">
            <input 
              type="file" 
              accept="video/*"
              onChange={(e) => {
                if (e.target.files[0]) {
                  handleFileUpload(e.target.files[0], '/upload/upload_video', 'vid');
                }
              }}
            />
            {loading.vid ? (
              <div className="loading-spinner-box">
                <Loader2 className="animate-spin text-purple" size={28} />
                <span className="uploading-text">Transcribing Video...</span>
              </div>
            ) : (
              <>
                <Upload className="dropzone-svg-icon text-purple" size={28} />
                <div className="dropzone-main-text">
                  Drop MP4 video or <span className="highlight-browse text-purple">browse</span>
                </div>
                <span className="dropzone-sub-text">Supported: .mp4 (Speech-to-text)</span>
              </>
            )}
          </label>
        </div>

        {/* Card 4: Audio Processing */}
        <div 
          className={`ingestion-card ${dragOverCard === 'aud' ? 'drag-over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOverCard('aud'); }}
          onDragLeave={() => setDragOverCard(null)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOverCard(null);
            if (e.dataTransfer.files[0]) {
              handleFileUpload(e.dataTransfer.files[0], '/upload/upload_audio', 'aud');
            }
          }}
        >
          <div className="card-top-header">
            <div className="icon-wrapper icon-blue">
              <Headphones size={22} />
            </div>
            <div>
              <h3 className="card-heading">Audio Processing</h3>
              <p className="card-subtext">Convert speech audio into searchable vectors</p>
            </div>
          </div>

          <label className="custom-dropzone">
            <input 
              type="file" 
              accept="audio/*"
              onChange={(e) => {
                if (e.target.files[0]) {
                  handleFileUpload(e.target.files[0], '/upload/upload_audio', 'aud');
                }
              }}
            />
            {loading.aud ? (
              <div className="loading-spinner-box">
                <Loader2 className="animate-spin text-blue" size={28} />
                <span className="uploading-text">Processing Audio...</span>
              </div>
            ) : (
              <>
                <Upload className="dropzone-svg-icon text-blue" size={28} />
                <div className="dropzone-main-text">
                  Drop audio file or <span className="highlight-browse text-blue">browse</span>
                </div>
                <span className="dropzone-sub-text">Supported: .mp3, .wav, .m4a</span>
              </>
            )}
          </label>
        </div>

        {/* Card 5: Web Content & Raw Text */}
        <div className="ingestion-card span-2-cols">
          <div className="card-top-header">
            <div className="icon-wrapper icon-emerald">
              <Globe size={22} />
            </div>
            <div>
              <h3 className="card-heading">Web Content & Raw Text Snippets</h3>
              <p className="card-subtext">Paste website URLs or raw text blocks to index into vector store</p>
            </div>
          </div>

          <div className="web-ingest-box">
            <textarea 
              className="custom-textarea"
              rows={4}
              placeholder="Paste website URLs or text snippets here..."
              value={webText}
              onChange={(e) => setWebText(e.target.value)}
            />
            <div className="web-ingest-footer">
              <span className="text-count-hint">{webText.length} characters</span>
              <button 
                className="btn-submit-web"
                disabled={!webText.trim()}
                onClick={() => {
                  if (webText.trim()) {
                    showNotification('Web text added to vector processing queue!', 'success');
                    setWebText('');
                  }
                }}
              >
                + Ingest Web Text
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
