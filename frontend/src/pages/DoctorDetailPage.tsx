import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { MapPin, Phone, Mail, Globe, Star, Award, Calendar, Building, ArrowLeft, CheckCircle, XCircle, FileText, ExternalLink } from 'lucide-react';
import SchedulingModal from '../components/SchedulingModal';
import { searchAuthorPublicationsJSON, PubMedPublication } from '../services/pubmed';

interface Provider {
  id: string;
  npi: string;
  name: string;
  specialty: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  phone: string;
  email?: string;
  website?: string;
  rating: number;
  yearsExperience: number;
  boardCertified: boolean;
  acceptingPatients: boolean;
  languages: string[];
  insurance: string[];
  education: {
    medicalSchool: string;
    graduationYear: number;
    residency: string;
  };
  // Additional professional information
  publications?: string[];
  books?: string[];
  lectures?: string[];
  specializations?: string[];
  fellowships?: string[];
  patientReviews?: Array<{
    rating: number;
    comment: string;
    date: string;
  }>;
  websites?: string[];
}

const DoctorDetailPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const provider = location.state?.provider as Provider;
  const [isSchedulingModalOpen, setIsSchedulingModalOpen] = useState(false);
  const [publications, setPublications] = useState<PubMedPublication[]>([]);
  const [isLoadingPublications, setIsLoadingPublications] = useState(false);
  const [searchTermsTried, setSearchTermsTried] = useState<string[]>([]);

  const openSchedulingModal = () => {
    setIsSchedulingModalOpen(true);
  };

  // Fetch PubMed publications when component loads
  useEffect(() => {
    const fetchPublications = async () => {
      if (!provider?.name) return;
      
      setIsLoadingPublications(true);
      const searchTerms: string[] = [];
      
      try {
        const doctorName = provider.name;
        let publications: PubMedPublication[] = [];
        
        // Strategy 1: Use [Full Author Name] field for most comprehensive search
        const nameParts = doctorName.split(' ');
        if (nameParts.length >= 2) {
          const lastName = nameParts[nameParts.length - 1];
          const firstName = nameParts[0];
          const fullAuthorSearch = `${lastName} ${firstName}`;
          
          searchTerms.push(`${fullAuthorSearch}[Full Author Name]`);
          console.log(`Trying search with full author name: ${fullAuthorSearch}[Full Author Name]`);
          publications = await searchAuthorPublicationsJSON(fullAuthorSearch, 5, true, 'full');
        }
        
        // Strategy 2: If no results, try with [Author] field as fallback
        if (publications.length === 0) {
          searchTerms.push(`"${doctorName}"[Author]`);
          console.log(`Trying fallback search with author field: "${doctorName}"[Author]`);
          publications = await searchAuthorPublicationsJSON(doctorName, 5, true, 'author');
        }
        
        setPublications(publications);
        setSearchTermsTried(searchTerms);
      } catch (error) {
        console.error('Error fetching publications:', error);
        setPublications([]);
      } finally {
        setIsLoadingPublications(false);
      }
    };

    fetchPublications();
  }, [provider?.name]);

  if (!provider) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-xl text-gray-600 mb-4">Provider not found</p>
          <button
            onClick={() => navigate('/')}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700"
          >
            Back to Search
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="min-h-screen bg-gray-50">
        <div className="container mx-auto px-4 py-8">
          {/* Back Button */}
          <button
            onClick={() => navigate('/results')}
            className="text-gray-900 hover:text-gray-700 mb-6 flex items-center"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Results
          </button>

          {/* Provider Header */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 mb-8">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between">
              <div className="flex-1">
                <div className="flex items-center mb-4">
                  <h1 className="text-4xl font-bold text-gray-900 mr-4">
                    {provider.name}
                  </h1>
                  <div className="flex items-center">
                    <Star className="h-6 w-6 text-yellow-400 fill-current" />
                    <span className="ml-2 text-xl text-gray-600">{provider.rating}</span>
                  </div>
                </div>

                <div className="flex items-center text-gray-600 mb-4">
                  <span className="text-xl font-medium">{provider.specialty}</span>
                  <span className="mx-3 text-2xl">•</span>
                  <Calendar className="h-5 w-5 mr-2" />
                  <span className="text-lg">{provider.yearsExperience} years experience</span>
                </div>

                {provider.boardCertified && (
                  <div className="flex items-center mb-4">
                    <Award className="h-5 w-5 text-blue-600 mr-2" />
                    <span className="text-blue-600 font-medium text-lg">Board Certified</span>
                  </div>
                )}

                <div className="flex items-center text-gray-600 mb-6">
                  <MapPin className="h-5 w-5 mr-2" />
                  <span className="text-lg">{provider.address}, {provider.city}, {provider.state} {provider.zip}</span>
                </div>

                {/* Status Badge */}
                <div className="mb-6">
                  <span className={`inline-flex items-center px-4 py-2 rounded-full text-lg font-medium ${
                    provider.acceptingPatients 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {provider.acceptingPatients ? (
                      <>
                        <CheckCircle className="h-5 w-5 mr-2" />
                        Accepting Patients
                      </>
                    ) : (
                      <>
                        <XCircle className="h-5 w-5 mr-2" />
                        Not Accepting Patients
                      </>
                    )}
                  </span>
                </div>
              </div>

              {/* Contact Actions */}
              <div className="lg:ml-8 mt-6 lg:mt-0">
                <div className="bg-blue-50 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Contact Information</h3>
                  
                  {provider.phone && (
                    <div className="flex items-center mb-3">
                      <Phone className="h-5 w-5 text-blue-600 mr-3" />
                      <span className="text-gray-700">{provider.phone}</span>
                    </div>
                  )}

                  {provider.email && (
                    <div className="flex items-center mb-3">
                      <Mail className="h-5 w-5 text-blue-600 mr-3" />
                      <span className="text-gray-700">{provider.email}</span>
                    </div>
                  )}

                  {provider.website && (
                    <div className="flex items-center mb-4">
                      <Globe className="h-5 w-5 text-blue-600 mr-3" />
                      <a 
                        href={provider.website} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        Visit Website
                      </a>
                    </div>
                  )}

                  <button 
                    onClick={openSchedulingModal}
                    className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors font-medium"
                  >
                    Schedule Appointment
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Detailed Information */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Education & Experience</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Medical School</h3>
                <div className="flex items-center">
                  <Building className="h-5 w-5 text-gray-500 mr-3" />
                  <div>
                    <p className="text-gray-900 font-medium">{provider.education.medicalSchool || 'No medical school listed'}</p>
                    <p className="text-gray-600">{provider.education.graduationYear ? `Graduated ${provider.education.graduationYear}` : 'No graduation year listed'}</p>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Residency</h3>
                <div className="flex items-center">
                  <Building className="h-5 w-5 text-gray-500 mr-3" />
                  <p className="text-gray-900">{provider.education.residency || 'No residency listed'}</p>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Experience</h3>
                <div className="flex items-center">
                  <Calendar className="h-5 w-5 text-gray-500 mr-3" />
                  <p className="text-gray-900">{provider.yearsExperience ? `${provider.yearsExperience} years of clinical practice` : 'No experience information available'}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Professional Achievements */}
          <div className="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Professional Achievements</h2>
            
            {/* PubMed Publications Section */}
            <div className="mb-8">
              <div className="flex items-center mb-4">
                <FileText className="h-6 w-6 text-blue-600 mr-3" />
                <h3 className="text-xl font-semibold text-gray-800">Recent Publications</h3>
                <span className="ml-2 text-sm text-gray-500 bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
                  PubMed
                </span>
                {publications.length > 0 && (
                  <span className="ml-2 text-sm text-gray-600 bg-green-100 text-green-800 px-2 py-1 rounded-full">
                    {publications.length} found
                  </span>
                )}
              </div>
              
              {isLoadingPublications ? (
                <div className="text-center py-8">
                  <div className="inline-flex items-center text-gray-500">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 mr-3"></div>
                    Searching PubMed for "{provider.name}"...
                  </div>
                </div>
              ) : publications.length > 0 ? (
                <div className="space-y-4">
                  {publications.map((pub) => (
                    <div key={pub.id} className="bg-gray-50 rounded-lg p-4 border-l-4 border-blue-500 hover:bg-gray-100 transition-colors">
                      <h4 className="font-medium text-gray-900 text-sm mb-2 leading-relaxed">
                        {pub.title}
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-600 mb-2">
                        <div>
                          <span className="font-medium">Authors:</span> {pub.authors.join(', ')}
                        </div>
                        <div>
                          <span className="font-medium">Journal:</span> {pub.journal}
                        </div>
                        <div>
                          <span className="font-medium">Published:</span> {pub.publicationDate}
                        </div>
                        <div>
                          <span className="font-medium">PMID:</span> {pub.pmid}
                        </div>
                      </div>
                      <div>
                        {pub.doi ? (
                          <a
                            href={`https://doi.org/${pub.doi}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center text-blue-600 hover:text-blue-800 hover:underline"
                          >
                            <ExternalLink className="h-3 w-3 mr-1" />
                            View on DOI
                          </a>
                        ) : (
                          <a
                            href={`https://pubmed.ncbi.nlm.nih.gov/${pub.pmid}/`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center text-blue-600 hover:text-blue-800 hover:underline"
                          >
                            <ExternalLink className="h-3 w-3 mr-1" />
                            View on PubMed
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <FileText className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                  <p>No recent publications found in PubMed</p>
                  <p className="text-sm mt-1">Searched for: "{provider.name}"</p>
                  {searchTermsTried.length > 1 && (
                    <div className="mt-2 text-xs">
                      <p className="font-medium mb-1">Search terms tried:</p>
                      <div className="space-y-1">
                        {searchTermsTried.map((term, index) => (
                          <code key={index} className="bg-gray-100 px-2 py-1 rounded text-gray-600">
                            {term}
                          </code>
                        ))}
                      </div>
                    </div>
                  )}
                  <p className="text-sm mt-3">This could mean the doctor hasn't published recently or uses a different name format in PubMed. We tried searching using the Full Author Name field and Author field.</p>
                </div>
              )}
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

              {/* Books & Book Chapters */}
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Books & Book Chapters</h3>
                {provider.books && provider.books.length > 0 ? (
                  <ul className="space-y-2">
                    {provider.books.map((book, index) => (
                      <li key={index} className="text-gray-600 text-sm">• {book}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-gray-500 italic">No books listed</p>
                )}
              </div>

              {/* Lectures & Courses */}
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Lectures & Courses Taught</h3>
                {provider.lectures && provider.lectures.length > 0 ? (
                  <ul className="space-y-2">
                    {provider.lectures.map((lecture, index) => (
                      <li key={index} className="text-gray-600 text-sm">• {lecture}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-gray-500 italic">No lectures listed</p>
                )}
              </div>

              {/* Specializations */}
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Specializations</h3>
                {provider.specializations && provider.specializations.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {provider.specializations.map((spec, index) => (
                      <span
                        key={index}
                        className="bg-purple-100 text-purple-800 px-3 py-1 rounded-full text-sm font-medium"
                      >
                        {spec}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 italic">No specializations listed</p>
                )}
              </div>

              {/* Fellowships */}
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Relevant Fellowships</h3>
                {provider.fellowships && provider.fellowships.length > 0 ? (
                  <ul className="space-y-2">
                    {provider.fellowships.map((fellowship, index) => (
                      <li key={index} className="text-gray-600 text-sm">• {fellowship}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-gray-500 italic">No fellowships listed</p>
                )}
              </div>

              {/* Years of Experience */}
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Years of Experience</h3>
                <p className="text-gray-600">{provider.yearsExperience || '--'} years of clinical practice</p>
              </div>
            </div>
          </div>

          {/* Patient Reviews */}
          <div className="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Patient Reviews</h2>
            
            {provider.patientReviews && provider.patientReviews.length > 0 ? (
              <div className="space-y-4">
                {provider.patientReviews.map((review, index) => (
                  <div key={index} className="border-l-4 border-blue-500 pl-4 py-2">
                    <div className="flex items-center mb-2">
                      <div className="flex items-center">
                        {[...Array(5)].map((_, i) => (
                          <Star
                            key={i}
                            className={`h-4 w-4 ${
                              i < review.rating
                                ? 'text-yellow-400 fill-current'
                                : 'text-gray-300'
                            }`}
                          />
                        ))}
                      </div>
                      <span className="ml-2 text-sm text-gray-500">{review.date}</span>
                    </div>
                    <p className="text-gray-700">{review.comment}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 italic">No patient reviews available</p>
            )}
          </div>

          {/* Websites */}
          <div className="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Websites</h2>
            
            {provider.websites && provider.websites.length > 0 ? (
              <div className="space-y-2">
                {provider.websites.map((website, index) => (
                  <a
                    key={index}
                    href={website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-blue-600 hover:text-blue-800 hover:underline"
                  >
                    {website}
                  </a>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 italic">No websites listed</p>
            )}
          </div>

          {/* Additional Information */}
          <div className="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Additional Information</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">NPI Number</h3>
                <p className="text-gray-600 font-mono">{provider.npi}</p>
              </div>
              
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Specialty</h3>
                <p className="text-gray-600">{provider.specialty}</p>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Languages Spoken</h3>
                {provider.languages && provider.languages.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {provider.languages.map((language, index) => (
                      <span
                        key={index}
                        className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium"
                      >
                        {language}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 italic">No languages listed</p>
                )}
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Insurance Accepted</h3>
                {provider.insurance && provider.insurance.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {provider.insurance.map((ins, index) => (
                      <span
                        key={index}
                        className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm font-medium"
                      >
                        {ins}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 italic">No insurance information available</p>
                )}
              </div>
            </div>
          </div>

          {/* Call to Action */}
          <div className="mt-8 bg-blue-600 rounded-lg p-8 text-center">
            <h2 className="text-2xl font-bold text-white mb-4">Ready to Schedule an Appointment?</h2>
            <p className="text-blue-100 mb-6">
              Contact {provider.name} directly to schedule your appointment or consultation.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              {provider.phone && (
                <a
                  href={`tel:${provider.phone}`}
                  className="bg-white text-blue-600 px-8 py-3 rounded-lg font-semibold hover:bg-gray-100 transition-colors"
                >
                  Call Now
                </a>
              )}
              {provider.email && (
                <a
                  href={`mailto:${provider.email}`}
                  className="bg-blue-700 text-white px-8 py-3 rounded-lg font-semibold hover:bg-blue-800 transition-colors"
                >
                  Send Email
                </a>
              )}
              <button 
                onClick={openSchedulingModal}
                className="bg-green-500 text-white px-8 py-3 rounded-lg font-semibold hover:bg-green-600 transition-colors"
              >
                Schedule Online
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Scheduling Modal */}
      <SchedulingModal
        isOpen={isSchedulingModalOpen}
        onClose={() => setIsSchedulingModalOpen(false)}
        provider={provider}
      />
    </>
  );
};



export default DoctorDetailPage;
