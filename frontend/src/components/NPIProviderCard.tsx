import React, { useState } from 'react';
import { MapPin, Phone, Star, Award, Calendar, Building, HelpCircle, Clock, FileText, Shield, ExternalLink, BookOpen } from 'lucide-react';
import { NPIProvider, ProviderContent, VumediContent, PubMedArticle } from '../services/api';
import SchedulingModal from './SchedulingModal';

interface NPIProviderCardProps {
  provider: NPIProvider;
  onClick?: (provider: NPIProvider) => void;
  isHighlighted?: boolean;
  grade?: string;
  providerContent?: ProviderContent;
}

export default function NPIProviderCard({ provider, onClick, isHighlighted = false, grade, providerContent }: NPIProviderCardProps) {
  const [isSchedulingModalOpen, setIsSchedulingModalOpen] = useState(false);
  const [isQuestionsModalOpen, setIsQuestionsModalOpen] = useState(false);
  const [isPreAuthModalOpen, setIsPreAuthModalOpen] = useState(false);
  const [isInsuranceModalOpen, setIsInsuranceModalOpen] = useState(false);

  const handleClick = () => {
    if (onClick) {
      onClick(provider);
    }
  };

  const openSchedulingModal = () => {
    setIsSchedulingModalOpen(true);
  };

  // Get grade color based on letter grade
  const getGradeColor = (grade: string): string => {
    if (grade.startsWith('A')) return 'bg-gradient-to-r from-emerald-500 to-green-600';
    if (grade.startsWith('B')) return 'bg-gradient-to-r from-blue-500 to-indigo-600';
    if (grade.startsWith('C')) return 'bg-gradient-to-r from-amber-500 to-orange-500';
    if (grade.startsWith('D')) return 'bg-gradient-to-r from-orange-500 to-red-500';
    return 'bg-gradient-to-r from-red-500 to-pink-600';
  };

  return (
    <>
      <div 
        className={`rounded-lg shadow-sm border p-6 hover:shadow-md transition-all cursor-pointer ${
          isHighlighted 
            ? 'bg-white border-2 border-yellow-400 shadow-lg' 
            : 'bg-white border border-gray-200'
        }`}
        onClick={handleClick}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Provider Header */}
            <div className="flex items-center mb-3">
              <h2 className="text-xl font-semibold text-gray-900 mr-3">
                {provider.name}
              </h2>
              {grade && (
                <div className={`inline-flex items-center justify-center w-8 h-8 ${getGradeColor(grade)} text-white text-sm font-bold rounded-lg shadow-sm`}>
                  {grade}
                </div>
              )}
              <div className="ml-3 flex items-center">
                <Award className="h-4 w-4 text-gray-400" />
                <span className="ml-1 text-sm text-gray-500 font-medium">Board Certified</span>
              </div>
            </div>

            {/* Specialty and Experience */}
            <div className="flex items-center text-gray-600 mb-3">
              <span className="font-medium">{provider.specialty}</span>
              <span className="mx-2">•</span>
              <Calendar className="h-4 w-4 mr-1" />
              <span>-- years of experience</span>
            </div>

            {/* Location */}
            <div className="flex items-center text-gray-600 mb-3">
              <MapPin className="h-4 w-4 mr-2" />
              <span>{provider.address}, {provider.city}, {provider.state} {provider.zip}</span>
            </div>

            {/* Contact Info */}
            <div className="flex items-center space-x-6 text-gray-600 mb-4">
              {provider.phone && (
                <div className="flex items-center">
                  <Phone className="h-4 w-4 mr-2" />
                  <span>{provider.phone}</span>
                </div>
              )}
            </div>

            {/* Additional Info */}
            <div className="mt-4">
              <span className="font-medium text-gray-700">Education:</span>
              <p className="text-gray-600 mt-1">--</p>
            </div>

            {/* Status */}
            <div className="mt-4">
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                Accepting Patients
              </span>
            </div>

            {/* Provider Content - Vumedi and PubMed */}
            {providerContent && (
              <div className="mt-4 space-y-3">
                {/* Vumedi Content */}
                {providerContent.vumedi_content && providerContent.vumedi_content.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                      <ExternalLink className="w-4 h-4 mr-1" />
                      Educational Videos
                    </h4>
                    <div className="space-y-2">
                      {providerContent.vumedi_content.map((content, index) => (
                        <a
                          key={index}
                          href={content.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="block p-2 bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors"
                        >
                          <div className="text-sm font-medium text-purple-800 break-words">
                            {content.title}
                          </div>
                          <div className="text-xs text-purple-600 mt-1">
                            View Video →
                          </div>
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* PubMed Articles */}
                {providerContent.pubmed_articles && providerContent.pubmed_articles.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                      <BookOpen className="w-4 h-4 mr-1" />
                      Research Articles
                    </h4>
                    <div className="space-y-2">
                      {providerContent.pubmed_articles.map((article, index) => (
                        <a
                          key={index}
                          href={`https://pubmed.ncbi.nlm.nih.gov/${article.pmid}/`}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="block p-2 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                        >
                          <div className="text-sm font-medium text-blue-800 break-words">
                            {article.title}
                          </div>
                          <div className="text-xs text-blue-600 mt-1">
                            PMID: {article.pmid} →
                          </div>
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col space-y-2 w-48 flex-shrink-0">
            <button 
              onClick={(e) => {
                e.stopPropagation();
                setIsQuestionsModalOpen(true);
              }}
              className="flex items-center justify-center space-x-2 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 transition-colors text-xs font-bold whitespace-nowrap"
            >
              <HelpCircle className="h-4 w-4" />
              <span>Questions to Ask</span>
            </button>
            
            <button 
              onClick={(e) => {
                e.stopPropagation();
                openSchedulingModal();
              }}
              className="flex items-center justify-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-xs font-bold whitespace-nowrap"
            >
              <Clock className="h-4 w-4" />
              <span>Book appointment</span>
            </button>
            
            <button 
              onClick={(e) => {
                e.stopPropagation();
                setIsPreAuthModalOpen(true);
              }}
              className="flex items-center justify-center space-x-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors text-xs font-bold whitespace-nowrap"
            >
              <FileText className="h-4 w-4" />
              <span>Pre-authorization Letter</span>
            </button>
            
            <button 
              onClick={(e) => {
                e.stopPropagation();
                setIsInsuranceModalOpen(true);
              }}
              className="flex items-center justify-center space-x-2 bg-orange-600 text-white px-4 py-2 rounded-lg hover:bg-orange-700 transition-colors text-xs font-bold whitespace-nowrap"
            >
              <Shield className="h-4 w-4" />
              <span>Insurance approval</span>
            </button>
          </div>
        </div>
      </div>

      {/* Scheduling Modal */}
      <SchedulingModal
        isOpen={isSchedulingModalOpen}
        onClose={() => setIsSchedulingModalOpen(false)}
        provider={provider}
      />

      {/* Questions Modal */}
      {isQuestionsModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-semibold text-gray-900">Questions to Ask Your Specialist</h3>
              <button
                onClick={() => setIsQuestionsModalOpen(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-4">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h4 className="font-semibold text-blue-900 mb-2">About Your Condition</h4>
                <ul className="text-blue-800 space-y-1 text-sm">
                  <li>• What is the exact diagnosis and what does it mean?</li>
                  <li>• What are the potential causes of this condition?</li>
                  <li>• How will this condition progress over time?</li>
                  <li>• What are the long-term implications?</li>
                </ul>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <h4 className="font-semibold text-green-900 mb-2">About Treatment Options</h4>
                <ul className="text-green-800 space-y-1 text-sm">
                  <li>• What are all available treatment options?</li>
                  <li>• What are the risks and benefits of each option?</li>
                  <li>• What is the recommended treatment and why?</li>
                  <li>• Are there any alternative or complementary treatments?</li>
                </ul>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg">
                <h4 className="font-semibold text-purple-900 mb-2">About Procedures/Surgery</h4>
                <ul className="text-purple-800 space-y-1 text-sm">
                  <li>• What does the procedure involve?</li>
                  <li>• What are the success rates and potential complications?</li>
                  <li>• What is the recovery process like?</li>
                  <li>• How many of these procedures have you performed?</li>
                </ul>
              </div>
              <div className="bg-orange-50 p-4 rounded-lg">
                <h4 className="font-semibold text-orange-900 mb-2">About Follow-up and Care</h4>
                <ul className="text-orange-800 space-y-1 text-sm">
                  <li>• What follow-up care will I need?</li>
                  <li>• What symptoms should I watch for?</li>
                  <li>• When should I contact you or seek emergency care?</li>
                  <li>• How will we monitor my progress?</li>
                </ul>
              </div>
            </div>
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setIsQuestionsModalOpen(false)}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Pre-authorization Modal */}
      {isPreAuthModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-semibold text-gray-900">Pre-authorization Letter Request</h3>
              <button
                onClick={() => setIsPreAuthModalOpen(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-4">
              <p className="text-gray-600">
                We'll help you generate a pre-authorization letter for your insurance company. 
                This letter will explain why the specialist consultation is medically necessary.
              </p>
              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-semibold text-gray-900 mb-2">Information Needed:</h4>
                <ul className="text-gray-700 space-y-1 text-sm">
                  <li>• Your insurance information</li>
                  <li>• Referring physician details (if applicable)</li>
                  <li>• Specific procedure codes (if known)</li>
                  <li>• Medical justification for the consultation</li>
                </ul>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <h4 className="font-semibold text-green-900 mb-2">What We'll Include:</h4>
                <ul className="text-green-800 space-y-1 text-sm">
                  <li>• Medical necessity justification</li>
                  <li>• Specialist qualifications and expertise</li>
                  <li>• Expected outcomes and benefits</li>
                  <li>• Cost-effectiveness analysis</li>
                </ul>
              </div>
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => setIsPreAuthModalOpen(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  // TODO: Implement pre-authorization letter generation
                  alert('Pre-authorization letter generation will be implemented soon!');
                  setIsPreAuthModalOpen(false);
                }}
                className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
              >
                Generate Letter
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Insurance Approval Modal */}
      {isInsuranceModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-semibold text-gray-900">Insurance Approval Assistance</h3>
              <button
                onClick={() => setIsInsuranceModalOpen(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-4">
              <p className="text-gray-600">
                We'll help you navigate the insurance approval process and gather the necessary information 
                to ensure your specialist consultation is covered.
              </p>
              
              <div className="bg-blue-50 p-4 rounded-lg">
                <h4 className="font-semibold text-blue-900 mb-3">Insurance Information</h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Insurance Company</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="e.g., Blue Cross Blue Shield"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Policy Number</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Enter your policy number"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Group Number (if applicable)</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Enter group number"
                    />
                  </div>
                </div>
              </div>

              <div className="bg-green-50 p-4 rounded-lg">
                <h4 className="font-semibold text-green-900 mb-3">Primary Care Physician Information</h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">PCP Name</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-green-500 focus:border-green-500"
                      placeholder="Dr. John Smith"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">PCP Address</label>
                    <textarea
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-green-500 focus:border-green-500"
                      rows={3}
                      placeholder="123 Main St, City, State 12345"
                    />
                  </div>
                </div>
              </div>

              <div className="bg-orange-50 p-4 rounded-lg">
                <h4 className="font-semibold text-orange-900 mb-2">Insurance Card Upload</h4>
                <p className="text-orange-800 text-sm mb-3">
                  Upload a clear photo of the front of your insurance card for verification.
                </p>
                <div className="border-2 border-dashed border-orange-300 rounded-lg p-4 text-center">
                  <svg className="mx-auto h-12 w-12 text-orange-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                    <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <p className="mt-2 text-sm text-orange-600">Click to upload or drag and drop</p>
                  <p className="text-xs text-orange-500">PNG, JPG up to 10MB</p>
                </div>
              </div>
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => setIsInsuranceModalOpen(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  // TODO: Implement insurance approval assistance
                  alert('Insurance approval assistance will be implemented soon!');
                  setIsInsuranceModalOpen(false);
                }}
                className="bg-orange-600 text-white px-4 py-2 rounded-lg hover:bg-orange-700 transition-colors"
              >
                Submit for Approval
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
